"""Exercise frozen multi-turn customer conversations through the versioned Agent."""

import json
from pathlib import Path

from app.agent.chat import EcomAgent
from app.infrastructure.database import action_proposals_table
from app.services.commerce import CommerceService
from sqlalchemy import func, select

from tests.test_customer_turn_finalization import DirectGateway
from tests.test_knowledge_platform import PlatformTestCase
from tests.test_policy_context import PolicyGateway, ScopedOrders

FIXTURE = Path(__file__).with_name("fixtures") / "policy-transfer-dialogues.json"


class DialogueGateway:
    client = None

    def select(self, turn, documents):
        self.draft = turn.get("draft") or documents[turn["draft_document"]]
        if "query" in turn:
            self.step = PolicyGateway({"query": turn["query"]} | turn.get("scope", {}))
        elif "order_id" in turn:
            self.step = PolicyGateway(
                {"order_id": turn["order_id"]}, name="query_order"
            )
        else:
            self.step = DirectGateway(self.draft)

    def complete(self, **kwargs):
        response = self.step.complete(**kwargs)
        response.choices[0].message.content = self.draft
        return response

    def parse(self, **kwargs):
        return self.step.parse(**kwargs)


class PolicyFollowupTransferTests(PlatformTestCase):
    def open_agent(self, session, gateway, *, commerce=None):
        agent = EcomAgent(
            config=self.config.model_copy(update={"memory_user_id": "user-1"}),
            session_path=session,
            model_gateway=gateway,
            commerce_service=commerce,
            strategy="react",
        )
        self.addCleanup(agent.release_resources)
        return agent

    def test_corrected_pending_payment_does_not_use_a_pending_settlement_policy(self):
        quote = (
            "预售尾款支付状态为待结算时，平台等待支付渠道返回清算结果，期间不再扣款。"
        )
        self.publish([self.ingest("clearing", quote)])
        gateway = DialogueGateway()
        agent = self.open_agent("payment-correction", gateway)
        query = "预售尾款显示待结算，系统会再扣尾款吗？"
        gateway.select({"query": query, "draft": quote}, {})
        self.assertEqual(agent.chat(query).evidence_state, "answerable")
        gateway.select({"query": query, "draft": quote}, {})
        changed = agent.chat("我刚刷新，显示支付失败了呢？")
        self.assertNotEqual(changed.evidence_state, "answerable")
        self.assertTrue(changed.requires_human)
        self.assertEqual(changed.citations, [])
        self.assertNotIn(quote, changed.reply)

    def test_change_of_product_preserves_order_or_user_scoped_conditions(self):
        clothes = "未拆吊牌的服饰在签收十二天内可申请退换。"
        bag = "未拆吊牌的书包在签收五天内可申请退换。"
        self.publish(
            [
                self.ingest("clothes", clothes, regions=["上海"], channels=["门店"]),
                self.ingest("bag", bag, regions=["北京"]),
            ]
        )
        cq = "服饰吊牌完整，签收后多久可以退货？"
        for owned in (True, False):
            with self.subTest(owned=owned):
                gateway = DialogueGateway()
                agent = self.open_agent(
                    str(owned), gateway, commerce=CommerceService(ScopedOrders())
                )
                scope = (
                    {"order_id": "ORD-OWNED"}
                    if owned
                    else {"region": "上海", "channel": "门店", "product": "服饰"}
                )
                intro = (
                    "请根据订单 ORD-OWNED 查退换规则。"
                    if owned
                    else "我在上海门店买了服饰，想核实退换规则。"
                )
                gateway.select({"query": cq, "scope": scope, "draft": clothes}, {})
                agent.chat(intro)
                gateway.select({"query": cq, "draft": clothes}, {})
                self.assertEqual(agent.chat(cq).evidence_state, "answerable")
                gateway.select({"query": "书包退货", "draft": bag}, {})
                result = agent.chat("那书包呢？")
                self.assertEqual(result.citations, [])
                self.assertTrue(result.requires_human)
                if owned:
                    self.assertEqual(result.evidence_state, "needs_clarification")
                    self.assertIn("订单", result.reply)
                    self.assertEqual(
                        agent._runtime_state["knowledge_context"]["order_id"],
                        "ORD-OWNED",
                    )
                else:
                    self.assertEqual(result.evidence_state, "no_evidence")
                    self.assertEqual(
                        gateway.step.observed_tools[-1]["context"],
                        {"region": "上海", "channel": "门店"},
                    )

    def test_legacy_session_marker_does_not_supply_an_unspecified_product(self):
        quote = "未拆吊牌的服饰在签收十二天内可申请退换。"
        self.publish([self.ingest("clothes", quote)])
        gateway = DialogueGateway()
        query = "服饰吊牌完整，签收后多久可以退货？"
        agent = self.open_agent("legacy-followup", gateway)
        gateway.select({"query": query, "draft": quote}, {})
        self.assertEqual(agent.chat(query).evidence_state, "answerable")
        agent._runtime_state.pop("policy_question", None)
        agent.save()
        restored = self.open_agent("legacy-followup", gateway)
        gateway.select({"query": query, "draft": quote}, {})
        result = restored.chat("它也适用吗？")
        self.assertEqual(result.evidence_state, "needs_clarification")
        self.assertEqual(result.citations, [])
        self.assertNotIn(quote, result.reply)

    def test_model_cannot_select_previous_order_or_remove_mismatched_selection_on_retry(
        self,
    ):
        quote = "门店的服饰签收十二天内可申请退货。"
        self.publish(
            [
                self.ingest(
                    "order-rule",
                    quote,
                    regions=["上海"],
                    channels=["门店"],
                    products=["服饰"],
                )
            ]
        )
        commerce = CommerceService(ScopedOrders())
        question = "服饰签收十二天退货"
        original = self.open_agent(
            "change-order",
            PolicyGateway({"query": question, "order_id": "ORD-OWNED"}),
            commerce=commerce,
        )
        self.assertEqual(
            original.chat("查订单 ORD-OWNED 的退货政策。").evidence_state, "answerable"
        )
        wrong_then_empty = PolicyGateway(
            [
                {"query": question, "order_id": "ORD-OWNED"},
                {"query": question},
            ]
        )
        restored = self.open_agent("change-order", wrong_then_empty, commerce=commerce)
        response = restored.chat("改查订单 ORD-EMPTY 的退货政策。")
        self.assertEqual(response.evidence_state, "needs_clarification")
        self.assertIn("订单", response.reply)
        self.assertEqual(response.citations, [])
        self.assertIn(
            "KNOWLEDGE_ORDER_SELECTION_REQUIRED",
            [row.get("error_code") for row in wrong_then_empty.observed_tools],
        )
        self.assertEqual(
            wrong_then_empty.observed_tools[-1]["error_code"],
            "KNOWLEDGE_CONTEXT_RECONFIRM_REQUIRED",
        )
        self.assertNotIn("order_id", restored._runtime_state["knowledge_context"])
        new = PolicyGateway({"query": question, "order_id": "ORD-EMPTY"})
        another = self.open_agent("change-order", new, commerce=commerce)
        self.assertEqual(
            another.chat("订单 ORD-EMPTY，请按这单核实。").evidence_state,
            "needs_clarification",
        )
        self.assertEqual(new.observed_tools[-1]["context"], {})
        self.assertEqual(
            another._runtime_state["knowledge_context"]["order_id"], "ORD-EMPTY"
        )
        mismatch = self.open_agent(
            "change-order",
            PolicyGateway({"query": question, "order_id": "ORD-EMPTY"}),
            commerce=commerce,
        )
        prompt = mismatch.chat("改查订单 ORD-OWNED 的退货政策。")
        self.assertEqual(prompt.evidence_state, "needs_clarification")
        self.assertIn("订单号", prompt.reply)
        self.assertEqual(prompt.citations, [])

    def run_dialogues(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        documents = fixture["documents"]
        release = self.publish(
            [self.ingest(key, text) for key, text in documents.items()]
        )
        source_ids = {
            hit["chunk_id"]: hit["document_id"]
            for hit in json.loads(self.k.release(release)["index_json"])
        }
        config = self.config.model_copy(update={"memory_user_id": "user-1"})
        results = []
        for dialogue in fixture["dialogues"]:
            agents = {}
            turns = []
            gateway = DialogueGateway()
            try:
                for turn in dialogue["turns"]:
                    session = dialogue["id"] + "-" + turn.get("session", "default")
                    if turn.get("restore"):
                        agents.pop(session).release_resources()
                    if session not in agents:
                        agents[session] = EcomAgent(
                            config=config,
                            session_path=session,
                            model_gateway=gateway,
                            strategy="react",
                        )
                    gateway.select(turn, documents)
                    agent = agents[session]
                    response = agent.chat(turn["user"])
                    tool = getattr(gateway.step, "observed_tools", [])
                    last_tool = tool[-1] if tool else {}
                    current_calls = []
                    for item in reversed(agent.raw_messages):
                        if item["role"] == "user":
                            break
                        current_calls.extend(
                            c["function"]["name"] for c in item.get("tool_calls", [])
                        )
                    with self.k.engine.connect() as connection:
                        proposals = connection.scalar(
                            select(func.count()).select_from(action_proposals_table)
                        )
                    actual = {
                        "state": response.evidence_state,
                        "reply": response.reply,
                        "follow_up": response.follow_up_question,
                        "documents": [
                            source_ids[c["chunk_id"]] for c in response.citations
                        ],
                        "requires_human": response.requires_human,
                        "tool_query": last_tool.get("query"),
                        "tool_outcome": last_tool.get("outcome"),
                        "tool_calls": current_calls,
                        "order_status": last_tool.get("order", {}).get("status"),
                        "proposals": proposals,
                    }
                    turns.append({"expected": turn, "actual": actual})
            finally:
                for agent in agents.values():
                    agent.release_resources()
            results.append({"id": dialogue["id"], "turns": turns})
        return {"documents": documents, "dialogues": results}

    def test_transfers_and_corrections(self):
        report = self.run_dialogues()
        for dialogue in report["dialogues"]:
            for record in dialogue["turns"]:
                expected, actual = record["expected"], record["actual"]
                with self.subTest(dialogue=dialogue["id"], user=expected["user"]):
                    self.assertEqual(actual["state"], expected["expect"])
                    self.assertEqual(actual["proposals"], 0)
                    if "query" in expected:
                        self.assertEqual(actual["tool_calls"], ["search_knowledge"])
                    if "order_id" in expected:
                        self.assertEqual(actual["tool_calls"], ["query_order"])
                        self.assertEqual(actual["order_status"], "delivered")
                    if "document" in expected:
                        quote = report["documents"][expected["document"]]
                        self.assertIn(quote, actual["reply"])
                        self.assertEqual(
                            set(actual["documents"]), {expected["document"]}
                        )
                        self.assertFalse(actual["requires_human"])
                    else:
                        self.assertEqual(actual["documents"], [])
                        if expected["expect"] == "not_requested":
                            self.assertEqual(actual["reply"], expected["draft"])
                        else:
                            self.assertTrue(actual["requires_human"])
                            if expected["expect"] == "needs_clarification":
                                self.assertRegex(
                                    actual["reply"], r"请.*(?:商品|业务|订单)"
                                )
                            else:
                                self.assertIn("核实", actual["reply"])
                            for quote in report["documents"].values():
                                self.assertNotIn(quote, actual["reply"])
