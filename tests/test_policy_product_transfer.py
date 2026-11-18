"""Synthetic public-search comparisons with product scope and contrasting clauses."""

from app.api import create_app
from fastapi.testclient import TestClient

from tests.test_knowledge_platform import PlatformTestCase

POLICIES = {
    "d01": "运动护具（包括护膝、护腕）吊牌完整时，签收十八天内可申请退货。",
    "d02": "未拆吊牌的护膝收纳袋在签收四天内可申请换货。",
    "d03": "未拆吊牌的保温壶在签收十二天内可申请退货。",
    "d04": "未拆吊牌的保温壶替换盖在签收六天内可申请换货。",
    "d05": "未拆吊牌的风衣在签收九天内可申请换货。",
    "d06": "未拆吊牌的风衣防尘罩在签收三天内可申请退货。",
}

# Each row specifies the public question, trusted product (if available), sole
# admissible source, and the reason for the label before running retrieval.
CASES = (
    (
        "t01",
        "签收第六天，护膝的吊牌还挂着，能退货吗？",
        "",
        "d01",
        "护膝明确列入十八天退货范围。",
    ),
    (
        "t02",
        "护腕吊牌保留着，收货十五天能申请退货吗？",
        "",
        "d01",
        "护腕是同一条款列明的另一子类。",
    ),
    (
        "t03",
        "运动护具未拆吊牌，签收后退货期限是多少天？",
        "",
        "d01",
        "条款直接规定运动护具的签收退货期限。",
    ),
    (
        "t04",
        "护膝收纳袋的吊牌完整，签收第三天还能换货吗？",
        "",
        "d02",
        "收纳袋专属条款允许四天内换货。",
    ),
    (
        "t05",
        "护膝收纳袋保留吊牌，签收第二天能申请退货吗？",
        "",
        None,
        "主品退货条款不涵盖收纳袋，收纳袋仅有换货依据。",
    ),
    (
        "t06",
        "刚签收两天，护膝吊牌没有剪，能申请换货吗？",
        "",
        None,
        "护膝只有退货依据，不能引用收纳袋的换货条款。",
    ),
    (
        "t07",
        "签收第五天，保温壶的吊牌还在，能退货吗？",
        "",
        "d03",
        "壶本体可在十二天内退。",
    ),
    (
        "t08",
        "保温壶替换盖吊牌未拆，收货第五天可以换货吗？",
        "",
        "d04",
        "替换盖可在六天内换。",
    ),
    (
        "t09",
        "保温壶替换盖未拆吊牌，签收三天能退货吗？",
        "",
        None,
        "替换盖只能找到换货规则，壶本体退货规则不能迁用。",
    ),
    (
        "t10",
        "保温壶未拆吊牌，签收三天能换货吗？",
        "",
        None,
        "壶身没有换货依据，替换盖的规则不能迁用。",
    ),
    (
        "t11",
        "风衣吊牌还在，收货第七天可以申请换货吗？",
        "风衣",
        "d05",
        "订单、问句及风衣专属换货条款一致。",
    ),
    (
        "t12",
        "风衣防尘罩吊牌没拆，签收两天可以退货吗？",
        "风衣防尘罩",
        "d06",
        "订单与独立出售的防尘罩退货条款一致。",
    ),
    (
        "t13",
        "风衣吊牌完整，签收两天能申请换货吗？",
        "风衣防尘罩",
        None,
        "订单是防尘罩，不能给风衣本体的换货结论。",
    ),
    (
        "t14",
        "护腕吊牌没摘，签收第五天可以申请退货吗？",
        "护膝",
        None,
        "虽有同一品类条款，所问具体商品与订单冲突。",
    ),
    (
        "t15",
        "吊牌还挂着，签收第五天可以退货吗？",
        "护腕",
        "d01",
        "问句省略商品，订单补足了处于明确范围的护腕。",
    ),
    (
        "t16",
        "风衣防尘罩未拆吊牌，签收两天可以换货吗？",
        "",
        None,
        "防尘罩只有退货条款，不能从名称中的风衣推断换货。",
    ),
)


class ProductTransferTests(PlatformTestCase):
    def setUp(self):
        super().setUp()
        self.client = TestClient(create_app(self.config))
        self.addCleanup(self.client.close)
        self.publish([self.ingest(doc, text) for doc, text in POLICIES.items()])

    def observe(self, question, product):
        response = self.client.post(
            "/v1/knowledge/search",
            headers={"X-API-Key": "user"},
            json={
                "query": question,
                "context": {"product": product} if product else {},
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        return {
            "outcome": data["outcome"],
            "grounded": data["grounded"],
            "documents": [hit["document_id"] for hit in data["results"]],
            "quotes": [citation["quote"] for citation in data["citations"]],
        }

    def test_public_search_returns_only_applicable_product_policy(self):
        for key, question, product, document, _ in CASES:
            with self.subTest(case=key):
                result = self.observe(question, product)
                self.assertEqual(
                    result["outcome"], "answerable" if document else "no_evidence"
                )
                self.assertEqual(result["grounded"], bool(document))
                self.assertEqual(
                    set(result["documents"]), {document} if document else set()
                )
                self.assertEqual(
                    set(result["quotes"]), {POLICIES[document]} if document else set()
                )
