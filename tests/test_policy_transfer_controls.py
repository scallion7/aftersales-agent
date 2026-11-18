"""Run prelabelled follow-up probes against the combined product and payment policies."""

import json
from pathlib import Path

from app.api import create_app
from fastapi.testclient import TestClient

from tests.test_knowledge_platform import PlatformTestCase
from tests.test_policy_payment_transitions import FIXTURE as PAYMENT_FIXTURE
from tests.test_policy_product_transfer import POLICIES as PRODUCT_POLICIES

CONTROLS = Path(__file__).with_name("fixtures") / "policy-transfer-controls.json"


class PolicyTransferControlTests(PlatformTestCase):
    def observe(self):
        documents = PRODUCT_POLICIES | {
            doc["id"]: doc["text"]
            for doc in json.loads(PAYMENT_FIXTURE.read_text())["policies"]
        }
        self.publish([self.ingest(key, text) for key, text in documents.items()])
        with TestClient(create_app(self.config)) as client:
            for case in json.loads(CONTROLS.read_text()):
                response = client.post(
                    "/v1/knowledge/search",
                    headers={"X-API-Key": "user"},
                    json={"query": case["question"]},
                )
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()
                actual = {
                    "outcome": result["outcome"],
                    "grounded": result["grounded"],
                    "documents": [hit["document_id"] for hit in result["results"]],
                    "quotes": [citation["quote"] for citation in result["citations"]],
                }
                document = case["document"]
                expected = {
                    "outcome": "answerable" if document else "no_evidence",
                    "grounded": bool(document),
                    "documents": [document] if document else [],
                    "quotes": [documents[document]] if document else [],
                }
                yield case | {
                    "expected": expected,
                    "observed": actual,
                    "passed": expected == actual,
                }

    def test_combined_product_and_payment_corpus(self):
        for case in self.observe():
            with self.subTest(case=case["id"]):
                self.assertEqual(case["observed"], case["expected"])
