"""Public retrieval and the delivered Agent answer have distinct evidence requirements."""

from uuid import uuid4

from app.agent.chat import EcomAgent
from app.api import create_app
from fastapi.testclient import TestClient

from tests.test_customer_turn_finalization import DirectGateway
from tests.test_knowledge_platform import PlatformTestCase
from tests.test_policy_context import PolicyGateway

GARMENT = "未拆吊牌的服饰在签收十天内可申请退换。"
BALANCE = "预售订单尾款截止日为活动页注明日期，超过日期须转人工处理，不自动扣款。"
MEMBER_BALANCE = "预售尾款未支付时，金牌会员不会自动扣款。"
WALLET_BALANCE = "仅绑定企业钱包的预售订单，超过日期仍未支付尾款时，系统将自动扣款。"

REVIEW_QUESTIONS = (
    ("衣服还保留吊牌，签收八天能退吗？", "garment", GARMENT),
    ("上周收到的外套吊牌完整，退货窗口多长？", "garment", GARMENT),
    ("我没付预售尾款，系统会自行扣钱吗？", "balance", BALANCE),
)
PARAPHRASES = (
    ("夹克吊牌没剪，收货后有几天可以换？", "garment", GARMENT),
    ("预售的尾款没交，平台会自己划走这笔钱吗？", "balance", BALANCE),
)
UNSUPPORTED = (
    ("耳机未拆吊牌，签收十天内能申请退换吗？", "garment"),
    ("书包未拆吊牌，签收十天内可申请退换吗？", "garment"),
    ("预售订单尾款已经付清，系统会重复扣款吗？", "balance"),
    ("预售订单尾款截止日之前，如何撤销已开通的自动扣款授权？", "balance"),
)


class QuotingGateway(PolicyGateway):
    """Model controls only its search wording and final draft, never the tool output."""

    def __init__(self, query, draft):
        super().__init__({"query": query})
        self.draft = draft

    def complete(self, **kwargs):
        reply = super().complete(**kwargs)
        reply.choices[0].message.content = self.draft
        return reply


class PolicyParaphraseTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.config = self.config.model_copy(
            update={"answer_evidence_check_enabled": True}
        )
        self.client = TestClient(create_app(self.config))
        self.addCleanup(self.client.close)

    def publish_base(self):
        self.publish(
            [
                self.ingest("garment", GARMENT, title="服饰退换"),
                self.ingest("balance", BALANCE, title="预售"),
            ]
        )

    def search(self, query, **parameters):
        response = self.client.post(
            "/v1/knowledge/search",
            headers={"X-API-Key": "user"},
            json={"query": query, **parameters},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def chat(self, question, gateway, *, strict=True):
        agent = EcomAgent(
            config=self.config.model_copy(
                update={"answer_evidence_check_enabled": strict}
            ),
            session_path=uuid4().hex,
            model_gateway=gateway,
            strategy="react",
        )
        try:
            return agent.chat(question)
        finally:
            agent.release_resources()

    def test_paraphrases_retrieve_applicable_original_passage(self):
        self.publish_base()
        for question, document, quote in REVIEW_QUESTIONS + PARAPHRASES:
            with self.subTest(question=question):
                response = self.search(question)
                self.assertEqual(response["outcome"], "answerable")
                self.assertEqual(
                    {hit["document_id"] for hit in response["results"]}, {document}
                )
                self.assertTrue(any(c["quote"] == quote for c in response["citations"]))

    def test_different_goods_paid_balance_and_cancelled_mandate_have_no_support(self):
        self.publish_base()
        for question, unrelated in UNSUPPORTED:
            with self.subTest(question=question):
                response = self.search(question)
                self.assertNotEqual(response["outcome"], "answerable")
                self.assertFalse(response["grounded"])
                self.assertNotIn(
                    unrelated, {hit["document_id"] for hit in response["results"]}
                )

    def test_unpaid_balance_needs_an_applicable_statement_about_unpaid_orders(self):
        for passage in (
            "预售订单尾款在超过截止日期后已经付清的，系统不再自动扣款。",
            WALLET_BALANCE,
            "预售尾款未支付会自动扣款吗？具体处理请查看订单。",
            "未付预售尾款的订单，将自动扣款一笔仓储费。",
            MEMBER_BALANCE,
            "关于预售尾款未支付后是否会自动扣款，请咨询平台。",
            "这项政策适用于上海门店。逾期未付预售尾款时不自动扣款。",
        ):
            self.publish([self.ingest("conditional", passage, version=uuid4().hex)])
            for question in (
                REVIEW_QUESTIONS[2][0],
                "预售订单尾款未支付，系统会自动扣款吗？",
            ):
                with self.subTest(passage=passage, question=question):
                    result = self.search(question)
                    self.assertNotEqual(result["outcome"], "answerable")
                    self.assertFalse(result["grounded"])

    def test_named_product_or_eligibility_allows_its_own_policy(self):
        bag = "未拆吊牌的书包在签收十天内可申请退换。"
        for question, query, passage, draft in (
            (
                UNSUPPORTED[1][0],
                "书包吊牌完整，签收后多久可申请退换？",
                bag,
                "书包保留吊牌，从签收起十天内可以申请退货或换货。",
            ),
            (
                "我是金牌会员，没付预售尾款，系统会自行扣钱吗？",
                "金牌会员的预售尾款没有支付，系统自动扣款吗？",
                MEMBER_BALANCE,
                "金牌会员没有支付预售尾款时，系统不会自行扣钱。",
            ),
            (
                "绑定企业钱包的预售订单，超过日期仍未支付尾款，系统会自动扣款吗？",
                "绑定企业钱包的预售订单逾期未付尾款，系统会自行扣钱吗？",
                WALLET_BALANCE,
                "仅对绑定企业钱包的预售订单，超过期限仍没付尾款时系统会自动扣款。",
            ),
        ):
            with self.subTest(question=question):
                self.publish([self.ingest("specific", passage, version=uuid4().hex)])
                result = self.search(question)
                self.assertEqual(result["outcome"], "answerable")
                self.assertIn(passage, [c["quote"] for c in result["citations"]])
                answer = self.chat(question, QuotingGateway(query, draft), strict=False)
                self.assertEqual(answer.evidence_state, "answerable")
                self.assertFalse(answer.requires_human)
                self.assertIn(answer.reply, (draft, passage))

    def test_clearance_exception_cannot_disappear_from_customer_answer(self):
        question = REVIEW_QUESTIONS[0][0]
        general = "您的衣服能退，签收十天内直接申请即可。"
        for passage in (
            GARMENT + "特卖商品除外。",
            "未拆吊牌的服饰在签收十天内可申请退换，特卖商品除外。",
        ):
            with self.subTest(passage=passage):
                self.publish([self.ingest("exception", passage, version=uuid4().hex)])
                result = self.search(question)
                if result["outcome"] == "answerable":
                    self.assertTrue(
                        any("特卖" in c["quote"] for c in result["citations"])
                    )
                answer = self.chat(
                    question, QuotingGateway(question, general), strict=False
                )
                self.assertNotIn(general, answer.reply)
                if answer.evidence_state == "answerable":
                    self.assertIn("特卖", answer.reply)
                    self.assertIn("吊牌", answer.reply)
                else:
                    self.assertTrue(
                        answer.requires_human
                        or answer.evidence_state == "needs_clarification"
                    )

    def test_paraphrasing_does_not_hide_missing_scope_or_conflict_beyond_top_one(self):
        self.publish(
            [
                self.ingest(
                    "garment",
                    GARMENT,
                    regions=["上海"],
                    policy_key="clothing",
                    decision="allow",
                ),
                self.ingest(
                    "exception",
                    "本地活动另行处理。",
                    regions=["上海"],
                    policy_key="clothing",
                    decision="review",
                ),
            ]
        )
        query = PARAPHRASES[0][0]
        for context, expected in (
            ({}, "needs_clarification"),
            ({"region": "北京"}, "no_evidence"),
            ({"region": "上海"}, "policy_conflict"),
        ):
            with self.subTest(context=context):
                result = self.search(query, context=context, top_k=1)
                self.assertEqual(result["outcome"], expected)
                self.assertFalse(result["grounded"])

    def test_agent_refuses_to_publish_a_bare_guess_when_model_skips_search(self):
        self.publish_base()
        for question, _, _ in REVIEW_QUESTIONS:
            with self.subTest(question=question):
                answer = self.chat(question, DirectGateway("可以。"))
                self.assertNotEqual(answer.reply, "可以。")
                self.assertTrue(answer.requires_human)
                self.assertEqual(answer.citations, [])
        lookup = PolicyGateway({"order_id": "ORD-20240125-006"}, name="query_order")
        # The injected model supplies a neutral receipt for an ordinary order lookup.
        lookup.parse = DirectGateway("订单状态已查询。").parse
        ordinary = self.chat(
            "帮我查一下已经付款的订单 ORD-20240125-006 现在是什么状态。", lookup
        )
        self.assertEqual(ordinary.evidence_state, "not_requested")
        self.assertEqual(ordinary.reply, "订单状态已查询。")

    def test_agent_delivers_quoted_policy_but_does_not_invent_a_longer_window(self):
        self.publish_base()
        for question, _, quote in REVIEW_QUESTIONS:
            with self.subTest(question=question):
                answer = self.chat(question, QuotingGateway(question, quote))
                self.assertEqual(answer.evidence_state, "answerable")
                self.assertFalse(answer.requires_human)
                self.assertEqual(answer.reply, quote)
                self.assertTrue(answer.citations)
        question = REVIEW_QUESTIONS[0][0]
        unsupported = "所有商品在签收三十天内均可退货。"
        answer = self.chat(question, QuotingGateway(question, unsupported))
        self.assertNotEqual(answer.reply, unsupported)
        self.assertTrue(answer.requires_human)

    def test_default_versioned_agent_never_publishes_invented_days_or_automatic_debit(
        self,
    ):
        self.publish_base()
        for question, _, quote in REVIEW_QUESTIONS:
            if quote == BALANCE:
                query = "预售订单尾款超过截止日期会自动扣款吗？"
                false_claim = "系统会自动扣除预售尾款。"
            else:
                query = "未拆吊牌的服饰在签收后多久可申请退换？"
                false_claim = "未拆吊牌的服饰在签收三十天内可申请退换。"
            with self.subTest(question=question):
                # Isolate delivery from recall: even the old index returns this
                # passage when the model rewrites the question in policy terms.
                self.assertEqual(self.search(query)["outcome"], "answerable")
                answer = self.chat(
                    question, QuotingGateway(query, false_claim), strict=False
                )
                self.assertNotIn(false_claim, answer.reply)
                if answer.evidence_state == "answerable":
                    self.assertTrue(answer.citations)
                    self.assertIn(quote, answer.reply)
                else:
                    self.assertTrue(answer.requires_human)
                    self.assertNotIn("三十天", answer.reply)

    def test_faithful_rewording_of_a_search_still_returns_the_qualified_policy(self):
        self.publish_base()
        for question, query, quote in (
            (REVIEW_QUESTIONS[1][0], "衣服吊牌完整，签收后的退货期限多长？", GARMENT),
            (REVIEW_QUESTIONS[2][0], "预售尾款未支付，系统会自动扣款吗？", BALANCE),
        ):
            with self.subTest(question=question):
                answer = self.chat(question, QuotingGateway(query, quote))
                self.assertEqual(answer.evidence_state, "answerable")
                self.assertFalse(answer.requires_human)
                self.assertEqual(answer.reply, quote)

    def test_default_agent_can_serve_a_faithfully_paraphrased_model_answer(self):
        self.publish_base()
        for question, draft, quote in (
            (
                REVIEW_QUESTIONS[1][0],
                "衣服吊牌完整的话，从签收起十天内可以申请退货或换货。",
                GARMENT,
            ),
            (
                REVIEW_QUESTIONS[2][0],
                "请以活动页给出的预售尾款日期为准，超过期限需人工处理，系统不会自行扣钱。",
                BALANCE,
            ),
        ):
            with self.subTest(question=question):
                answer = self.chat(
                    question, QuotingGateway(question, draft), strict=False
                )
                self.assertEqual(answer.evidence_state, "answerable")
                self.assertFalse(answer.requires_human)
                self.assertTrue(answer.citations)
                self.assertIn(answer.reply, (draft, quote))

    def test_truncated_tool_query_cannot_remove_the_original_goods_or_payment_condition(
        self,
    ):
        self.publish_base()
        # Each short tool query is intentionally answerable on its own. It dropped
        # the actual customer's product or changed the payment state in the request.
        for question, query, quote in (
            (UNSUPPORTED[0][0], "未拆吊牌的服饰在签收十天内可申请退换", GARMENT),
            (UNSUPPORTED[2][0], "预售尾款截止日不自动扣款", BALANCE),
            (UNSUPPORTED[3][0], "预售尾款截止日不自动扣款", BALANCE),
        ):
            with self.subTest(question=question):
                self.assertEqual(self.search(query)["outcome"], "answerable")
                answer = self.chat(question, QuotingGateway(query, quote))
                self.assertNotEqual(answer.evidence_state, "answerable")
                self.assertNotEqual(answer.reply, quote)
                self.assertTrue(answer.requires_human)
