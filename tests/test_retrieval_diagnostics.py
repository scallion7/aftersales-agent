"""Diagnostics must preserve public ranking and explain rejected candidates."""

from app.platform.retrieval import HybridRetrieval

from tests.test_knowledge_platform import PlatformTestCase


class RetrievalDiagnosticTests(PlatformTestCase):
    def test_diagnostic_parity_with_filtering_rank_and_cache_bypass(self):
        self.publish(
            [
                self.ingest("valid"),
                self.ingest("future", effective_date="2099-01-01"),
                self.ingest("expired", expires_at="2021-01-01"),
                self.ingest("region", regions=["上海"]),
            ]
        )
        retriever = HybridRetrieval(self.config)
        for mode in ("vector", "bm25", "hybrid"):
            kwargs = {"mode": mode, "day": "2026-01-01", "context": {"region": "北京"}}
            public = retriever.search("七天退货政策", **kwargs)
            trace = retriever.diagnose("七天退货政策", **kwargs)
            self.assertEqual(public["results"], trace["results"])
            self.assertEqual(public["outcome"], trace["outcome"])
            self.assertNotIn("diagnostics", public)
            diagnostics = trace["diagnostics"]
            self.assertTrue(diagnostics["cache_bypassed"])
            rows = {r["document_id"]: r for r in diagnostics["candidates"]}
            self.assertIn("not_yet_effective", rows["future"]["filter_reasons"])
            self.assertIn("region_mismatch", rows["region"]["filter_reasons"])
            self.assertTrue(rows["valid"]["selected"])
            self.assertEqual(rows["valid"]["final_rank"], 1)

    def test_lexical_guard_reports_reason_and_original_score(self):
        self.publish([self.ingest("sparse", text="七天退货")])
        result = HybridRetrieval(self.config).diagnose(
            "七天退货 包装 发票 门店 线上 苹果 食品 物流运费"
        )
        row = result["diagnostics"]["candidates"][0]
        self.assertGreater(row["score"], 0)
        self.assertEqual(row["selection_reason"], "lexical_support_rejected")
        self.assertFalse(row["selected"])
        self.assertEqual(result["outcome"], "no_evidence")

    def test_scoped_vector_query_recovers_the_coat_clause_with_both_indexes(self):
        self.publish(
            [
                self.ingest("apparel", "未拆吊牌的服饰在签收十天内可申请退换。"),
                self.ingest("gifts", "本月会员礼品在收到后可以登记。"),
            ]
        )
        for compiled in (False, True):
            retriever = HybridRetrieval(
                self.config.model_copy(update={"compiled_retrieval_enabled": compiled})
            )
            with self.subTest(compiled=compiled):
                result = retriever.diagnose(
                    "上周收到的外套吊牌完整，退货窗口多长？", mode="vector"
                )
                self.assertEqual(result["outcome"], "answerable")
                self.assertEqual(
                    [r["document_id"] for r in result["results"]], ["apparel"]
                )
                row = next(
                    r
                    for r in result["diagnostics"]["candidates"]
                    if r["document_id"] == "apparel"
                )
                self.assertGreater(row["vector_score"], 0)
                self.assertTrue(row["in_candidate_pool"])
                self.assertTrue(row["policy_evidence"]["supported"])
                for product, outcome in (
                    ("耳机", "no_evidence"),
                    ("外套", "answerable"),
                ):
                    filtered = retriever.search(
                        "上周收到的外套吊牌完整，退货窗口多长？",
                        context={"product": product},
                        mode="vector",
                    )
                    self.assertEqual(filtered["outcome"], outcome)

    def test_empty_release_has_complete_diagnostic_envelope(self):
        result = HybridRetrieval(self.config).diagnose("退货政策")
        self.assertEqual(result["diagnostics"]["outcome_reason"], "no_evidence")
        self.assertEqual(result["diagnostics"]["candidates"], [])

    def test_conversational_installation_question_preserves_scope_and_abstention(self):
        self.publish(
            [self.ingest("install", "家电预约安装请联系门店。", regions=["上海"])]
        )
        question = "请问烤箱到家以后什么时候预约安装？"
        for compiled in (False, True):
            retriever = HybridRetrieval(
                self.config.model_copy(update={"compiled_retrieval_enabled": compiled})
            )
            for mode in ("bm25", "vector", "hybrid"):
                for query, context, outcome in (
                    (question, {"region": "上海"}, "answerable"),
                    (question, {}, "needs_clarification"),
                    (question, {"region": "北京"}, "no_evidence"),
                    ("可以预约宠物体检吗？", {"region": "上海"}, "no_evidence"),
                    ("请问可以吗？", {"region": "上海"}, "no_evidence"),
                ):
                    with self.subTest(
                        compiled=compiled, mode=mode, context=context, query=query
                    ):
                        result = retriever.search(query, context=context, mode=mode)
                        self.assertEqual(result["outcome"], outcome)
                        if outcome == "no_evidence":
                            self.assertEqual(result["citations"], [])

    def test_overlapping_subwords_cannot_outvote_the_product_in_a_conflict(self):
        self.publish(
            [
                self.ingest(
                    "short", "硬盘保修一年。", policy_key="disk", decision="one"
                ),
                self.ingest(
                    "long", "硬盘保修两年。", policy_key="disk", decision="two"
                ),
                self.ingest("other", "键盘保修期从签收开始，换货期限为一个月。"),
            ]
        )
        for compiled in (False, True):
            retriever = HybridRetrieval(
                self.config.model_copy(update={"compiled_retrieval_enabled": compiled})
            )
            for mode in ("bm25", "vector", "hybrid"):
                with self.subTest(compiled=compiled, mode=mode):
                    result = retriever.diagnose("硬盘的保修期限到底是多少？", mode=mode)
                    self.assertEqual(result["outcome"], "policy_conflict")
                    self.assertEqual(
                        {r["document_id"] for r in result["results"]}, {"short", "long"}
                    )
                    other = next(
                        r
                        for r in result["diagnostics"]["candidates"]
                        if r["document_id"] == "other"
                    )
                    self.assertGreater(len(other["matched_tokens"]), 1)
                    self.assertEqual(len(other["evidence_matches"]), 1)
