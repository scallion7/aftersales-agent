"""Public responses, persisted history and optional memory agree on the final answer."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.agent.chat import EcomAgent
from app.multi_agent.orchestrator import MultiAgentOrchestrator
from app.repositories.runs import RunInterrupted
from app.repositories.session import SqlSessionRepository
from app.schemas.response import CustomerServiceResponse
from app.services.actions import ActionService

from tests.test_knowledge_platform import PlatformTestCase
from tests.test_policy_context import PolicyGateway


class DirectGateway:
    client = None

    def __init__(self, text="请联系客服。", **metadata):
        self.text = text
        self.metadata = metadata
        self.history = []

    def complete(self, *, messages, purpose, **_):
        self.history = messages
        text = "postsale" if purpose == "router" else self.text
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))
            ]
        )

    def parse(self, **_):
        response = CustomerServiceResponse(
            intent="greeting", confidence=1, reply=self.text, **self.metadata
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=response))]
        )


class CustomerTurnTests(PlatformTestCase):
    def agent(self, gateway, session="turn", *, multi=False):
        cls = MultiAgentOrchestrator if multi else EcomAgent
        agent = cls(
            config=self.config.model_copy(
                update={"history_threshold": 100, "answer_evidence_check_enabled": True}
            ),
            session_path=session,
            model_gateway=gateway,
            strategy="react",
        )
        self.addCleanup(agent.release_resources)
        return agent

    def test_no_tool_single_and_multi_require_evidence_despite_greeting_label(self):
        for multi in (False, True):
            agent = self.agent(
                DirectGateway("当然可以。"), f"direct-{multi}", multi=multi
            )
            response = agent.chat("订单号 ORD-01 已签收八天，还能退吗？")
            self.assertEqual(
                (response.evidence_state, response.requires_human, response.citations),
                ("no_evidence", True, []),
            )
            self.assertNotIn("当然可以", repr(agent.raw_messages))
            restored = self.agent(
                DirectGateway("可以。"), f"direct-{multi}", multi=multi
            )
            self.assertEqual(restored.chat("那门店呢？").evidence_state, "no_evidence")

    def test_fee_and_membership_questions_need_evidence_without_explicit_policy_words(
        self,
    ):
        for question, answer in (
            ("退货运费谁出？", "商家承担。"),
            ("没拆封退货要收手续费吗？", "不收。"),
            ("会员积分会过期吗？", "不会过期。"),
            ("退货邮费谁出？", "卖家包。"),
        ):
            with self.subTest(question=question):
                result = self.agent(DirectGateway(answer)).chat(question)
                self.assertEqual(result.evidence_state, "no_evidence")
                self.assertNotEqual(result.reply, answer)
        result = self.agent(DirectGateway("目前正在处理中。")).chat(
            "可以帮我查退货运费退款进度吗？"
        )
        self.assertEqual(result.evidence_state, "not_requested")

    def test_followup_alone_cannot_assert_an_ungrounded_policy(self):
        agent = self.agent(
            DirectGateway("您好。", follow_up_question="所有订单都包邮，要下单吗？")
        )
        result = agent.chat("你好")
        self.assertEqual(result.evidence_state, "no_evidence")
        self.assertIsNone(result.follow_up_question)
        self.assertNotIn(
            "所有订单都包邮", str(agent.session_repository.load()["messages"])
        )
        agent = self.agent(
            DirectGateway("您好。", follow_up_question="需要我帮您介绍退换货政策吗？")
        )
        result = agent.chat("你好")
        self.assertEqual(result.evidence_state, "not_requested")
        self.assertEqual(result.follow_up_question, "需要我帮您介绍退换货政策吗？")

    def test_journal_replayed_lookup_restores_authoritative_evidence(self):
        self.publish([self.ingest(text="服饰签收七天内可以退货。")])
        agent = self.agent(PolicyGateway({"query": "服饰签收七天退货"}))
        recorded = agent.knowledge_service.search("服饰签收七天退货")
        self.assertEqual(recorded["outcome"], "answerable")
        with patch.object(
            agent.tool_manager.execution_service,
            "execute",
            return_value=json.dumps(recorded),
        ):
            result = agent.chat("请核实退货政策。")
        self.assertEqual(result.evidence_state, "answerable")
        self.assertEqual(result.citations, recorded["citations"])

    def test_fabricated_evidence_and_followup_are_discarded(self):
        self.publish([self.ingest()])
        agent = self.agent(
            DirectGateway(
                "完全可以。",
                evidence_state="answerable",
                citations=[{"release_id": "made-up"}],
                follow_up_question="按此办理？",
            )
        )
        result = agent.chat("请核对我的申请。")
        self.assertEqual(result.evidence_state, "no_evidence")
        self.assertEqual(result.citations, [])
        self.assertIsNone(result.follow_up_question)

    def test_social_and_order_requests_exit_policy_context_without_hiding_mixed_questions(
        self,
    ):
        gateway = DirectGateway("当前仍在处理中。")
        agent = self.agent(gateway)
        for text in (
            "你好",
            "可以帮我查退款进度吗？",
            "查一下订单 ORD-001 到哪了？",
            "怎么换收货地址",
            "订单里的退款金额是多少",
            "我的快递还有多久能送达",
            "我想投诉客服态度",
            "帮我取消订单",
            "你好，先列出我名下的订单，随后我会询问适用规则。",
        ):
            agent._runtime_state["policy_followup"] = "needs_clarification"
            with self.subTest(text=text):
                self.assertEqual(agent.chat(text).evidence_state, "not_requested")
        for text in (
            "你好，耳机保修多久？",
            "请查询订单 ORD-001 退款进度，另外还能退货吗？",
        ):
            self.assertEqual(agent.chat(text).evidence_state, "no_evidence")
        gateway.text = "您好，我可以帮您介绍退换货政策。"
        self.assertEqual(agent.chat("你好").evidence_state, "not_requested")
        gateway.text = "所有服饰都可以退货。"
        self.assertEqual(agent.chat("你好").evidence_state, "no_evidence")

    def test_clarification_history_and_memory_use_only_published_answer(self):
        self.publish([self.ingest(text="服饰签收七天内可以退货。", regions=["上海"])])
        agent = self.agent(PolicyGateway({"query": "服饰签收七天退货"}))
        agent.memory_manager.memory_enabled = True
        with patch.object(agent.memory_manager, "update_short_term") as memory:
            response = agent.chat("服饰七天能退货吗？")
        self.assertEqual(response.evidence_state, "needs_clarification")
        history = agent.session_repository.load()["messages"]
        assistants = [m for m in history if m["role"] == "assistant"]
        self.assertEqual(
            [m["content"] for m in assistants if m.get("tool_calls")], [""]
        )
        self.assertEqual(
            [
                json.loads(m["content"])["reply"]
                for m in assistants
                if not m.get("tool_calls")
            ],
            [response.reply],
        )
        self.assertEqual(
            memory.call_args.args[0],
            [
                {"role": "user", "content": "服饰七天能退货吗？"},
                {"role": "assistant", "content": response.reply},
            ],
        )

    def test_old_session_keeps_tool_trace_and_standalone_replies_but_discards_replaced_draft(
        self,
    ):
        repo = SqlSessionRepository(
            self.config.database_url, "legacy", self.config.memory_user_id
        )
        final = CustomerServiceResponse(
            intent="after_sale", confidence=1, reply="请补充地区。"
        ).model_dump_json()
        rows = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "您好"},
            {"role": "user", "content": "规则是什么？"},
            {
                "role": "assistant",
                "tool_calls": [{"id": "abc"}],
                "content": "未审核的中间推断",
            },
            {"role": "tool", "tool_call_id": "abc", "content": "{}"},
            {"role": "assistant", "content": "未审核的退货承诺"},
            {"role": "assistant", "content": final},
        ]
        repo.save(rows, None, {})
        agent = self.agent(DirectGateway("您好"), "legacy")
        for history in (agent.messages, agent.raw_messages):
            self.assertNotIn("未审核", str(history))
            self.assertIn("您好", str(history))
            self.assertIn("tool_call_id", str(history))
            self.assertIn("请补充地区", str(history))

    def test_unrelated_pending_action_keeps_its_card_and_does_not_replace_policy_answer(
        self,
    ):
        self.publish([self.ingest(text="服饰签收七天内可以退货。")])
        actions = ActionService(self.config.database_url)
        old = actions.propose(
            self.config.memory_user_id,
            "turn",
            "create_after_sale_case",
            {"order_id": "ORD-OLD", "reason": "破损"},
            "v1",
        )
        agent = self.agent(PolicyGateway({"query": "服饰签收七天退货"}))
        response = agent.chat("服饰签收七天能退货吗？")
        self.assertEqual(response.reply, "服饰签收七天内可以退货。")
        self.assertEqual(
            actions.pending(self.config.memory_user_id, "turn")[0]["action_id"],
            old["action_id"],
        )

    def test_optional_memory_timeout_preserves_reply_and_ownership_interruption_propagates(
        self,
    ):
        agent = self.agent(DirectGateway("您好。"))
        agent.memory_manager.memory_enabled = True
        agent.memory_manager.stm.facts = ["上轮偏好"]
        with patch.object(
            agent.memory_manager, "update_short_term", side_effect=TimeoutError
        ):
            response = agent.chat("你好")
        stored = agent.session_repository.load()
        self.assertEqual(
            json.loads(stored["messages"][-1]["content"])["reply"], response.reply
        )
        self.assertEqual(stored["short_term_memory"]["facts"], ["上轮偏好"])
        self.assertEqual(
            stored["short_term_memory"]["runtime_state"]["pending_memory_turns"],
            [["你好", response.reply]],
        )
        agent = self.agent(DirectGateway("再见。"))
        agent.memory_manager.memory_enabled = True
        with patch.object(agent.memory_manager, "update_short_term") as memory:
            agent.chat("再见")
            self.assertEqual(
                [m["content"] for m in memory.call_args.args[0]],
                ["你好", response.reply, "再见", "再见。"],
            )
            self.assertNotIn("pending_memory_turns", agent._runtime_state)
            agent.chat("感谢")
            self.assertEqual(
                [m["content"] for m in memory.call_args.args[0]], ["感谢", "再见。"]
            )
        with patch.object(
            agent.memory_manager,
            "update_short_term",
            side_effect=RunInterrupted("RUN_FENCED"),
        ):
            with self.assertRaises(RunInterrupted):
                agent.chat("再见")
