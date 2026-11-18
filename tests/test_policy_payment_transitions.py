"""Exercise payment status, monetary object, and action through public knowledge search."""

import json
from pathlib import Path

from app.api import create_app
from fastapi.testclient import TestClient

from tests.test_knowledge_platform import PlatformTestCase

FIXTURE = Path(__file__).with_name("fixtures") / "policy-transfer-payments.json"


class PaymentTransitionTests(PlatformTestCase):
    def public_search_cases(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        policies = {policy["id"]: policy for policy in fixture["policies"]}
        self.publish(
            [
                self.ingest(key, policy["text"], title=policy["title"])
                for key, policy in policies.items()
            ]
        )
        with TestClient(create_app(self.config)) as client:
            for case in fixture["cases"]:
                response = client.post(
                    "/v1/knowledge/search",
                    headers={"X-API-Key": "user"},
                    json={"query": case["query"]},
                )
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                docs = sorted({hit["document_id"] for hit in result["results"]})
                quotes = [citation["quote"] for citation in result["citations"]]
                expected = case["expected"]
                if expected:
                    correct = (
                        result["outcome"] == "answerable"
                        and result["grounded"]
                        and docs == [expected]
                        and quotes == [policies[expected]["text"]]
                    )
                else:
                    correct = (
                        result["outcome"] == "no_evidence"
                        and not result["grounded"]
                        and not docs
                        and not quotes
                    )
                yield {
                    **case,
                    "expected_quote": policies[expected]["text"] if expected else None,
                    "outcome": result["outcome"],
                    "documents": docs,
                    "quotes": quotes,
                    "passed": correct,
                }

    def test_search_requires_the_current_state_and_the_requested_action(self):
        for result in self.public_search_cases():
            with self.subTest(case=result["id"]):
                self.assertTrue(result["passed"], result)

    def test_named_payment_page_actor_and_account_stay_with_their_action(self):
        reversed_rule = "预售尾款付款交易已成功撤回时，买家需要在订单页重新支付尾款。"
        wallet_rule = "预售尾款只支付了一部分时，平台会从企业钱包自动补扣尾款。"
        human_rule = "预售尾款待结算时，人工客服不会再扣尾款。"
        self.publish(
            [
                self.ingest("page", reversed_rule),
                self.ingest("wallet", wallet_rule),
                self.ingest("human", human_rule),
            ]
        )
        questions = (
            ("预售尾款交易撤回成功，我应该在哪里重新支付尾款？", "page"),
            ("预售尾款交易撤回成功，买家要在订单页重新支付尾款吗？", "page"),
            ("预售尾款交易撤回成功，买家要在活动页重新支付尾款吗？", None),
            ("预售尾款交易撤回成功，平台要在订单页重新支付尾款吗？", None),
            ("预售尾款只付了一半，系统会从企业钱包自动补扣尾款吗？", "wallet"),
            ("预售尾款只付了一半，系统会从银行卡自动补扣尾款吗？", None),
            ("预售尾款待结算，人工客服会不会再扣尾款？", "human"),
            ("预售尾款待结算，平台会不会再扣尾款？", None),
            ("预售尾款先支付失败，后来全额付清并到账，还会再催我交尾款吗？", None),
        )
        with TestClient(create_app(self.config)) as client:
            for question, document in questions:
                with self.subTest(question=question):
                    result = client.post(
                        "/v1/knowledge/search",
                        headers={"X-API-Key": "user"},
                        json={"query": question},
                    )
                    self.assertEqual(result.status_code, 200, result.text)
                    hits = result.json()["results"]
                    self.assertEqual(
                        {hit["document_id"] for hit in hits},
                        {document} if document else set(),
                    )

    def test_correction_requires_a_single_stated_status_for_one_charge(self):
        from app.platform.payment_conditions import (
            parse_payment_state,
            replace_payment_state,
        )

        self.assertEqual(parse_payment_state("尾款只付了一半"), "partial")
        self.assertEqual(
            replace_payment_state("尾款只付了一半，会扣钱吗？", "改成待结算"),
            "尾款待结算，会扣钱吗？",
        )
        self.assertIsNone(
            replace_payment_state("尾款没付，系统会扣款吗？", "定金已经支付")
        )
        for ambiguous in (
            "预售定金付清，尾款还没付",
            "预售尾款先支付失败，随后已结清到账",
            "预售尾款不是待结算",
        ):
            self.assertIsNone(replace_payment_state(ambiguous, "尾款已结清到账"))
