# 实验参考答案

[课程路线](README.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md) · [项目展示](../showcase/README.md)

下面给出九个作业的参考实现。先完成自己的预测和测试，再对照答案。每段代码是一个测试方法，需放入指定文件的指定测试类，代码块按顶层展示，粘贴到类中时整体增加四个空格缩进。文件原有导入与 fixture 会被复用；代码中的额外导入已写在方法内。不要把多个测试类的片段放进同一个类。

`test_learning_*` 是供学员添加的方法名称，仓库基线没有这些方法。下方命令只在加入对应方法后运行；未写作业时，请使用各层文档中的“基线验证”。参考实现只操作临时数据，不调用真实模型、真实退款或原冻结保留集。验收自己的改动时，同时重新运行相应实验的原有基线。

## L1-01：注入固定回复

位置为 [tests/test_architecture.py](../../tests/test_architecture.py) 的 `ApplicationFactoryTests`。原测试 `test_factory_injects_client_and_config_into_single_agent` 检查注入对象和保存，新用例检查可控回复字段。置信度来自 fixture，不能解释成校准过的业务概率。

```python
def test_learning_injected_reply(self):
    with tempfile.TemporaryDirectory() as tmp:
        config = Settings(
            _env_file=None,
            openai_api_key="offline",
            database_url=f"sqlite:///{tmp}/lab.db",
            session_path=str(Path(tmp) / "session.json"),
            memory_enabled=False,
            skills_enabled=False,
            mcp_enabled=False,
        )
        expected = CustomerServiceResponse(
            intent=IntentType.GREETING,
            confidence=0.42,
            reply="欢迎进入售后实验",
        )
        client = FakeOpenAI()
        client.beta.chat.completions.parse = lambda **_: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(parsed=expected))]
        )
        agent = create_agent(mode="single", config=config, client=client)
        try:
            result = agent.chat("你好")
            self.assertEqual(result.reply, expected.reply)
            self.assertEqual(result.confidence, 0.42)
            self.assertTrue(Path(config.session_path).is_file())
        finally:
            agent.close()
```

作业验收命令。

```bash
python -m unittest tests.test_architecture.ApplicationFactoryTests.test_learning_injected_reply -v
```

## L1-02：参数负例

位置为 [tests/test_plan_execution.py](../../tests/test_plan_execution.py) 的 `ToolContractTests`。参数 schema 检查发生在注册表调用处理器前，MCP 的签名身份和写操作确认属于另外的检查层；参考原 `test_registry_rejects_invalid_arguments_before_handler`。

```python
def test_learning_invalid_search_arguments(self):
    with tempfile.TemporaryDirectory() as tmp:
        config = Settings(
            _env_file=None,
            database_url=f"sqlite:///{tmp}/tools.db",
            openai_api_key="offline",
            observability_enabled=False,
            memory_enabled=False,
            skills_enabled=False,
            mcp_enabled=False,
        )
        registry = create_default_tool_registry(config=config)
        cases = (
            {},
            {"query": "退货", "top_k": 0},
            {"query": "退货", "user_id": "admin"},
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = json.loads(registry.execute("search_knowledge", arguments))
                self.assertEqual(result["error_code"], "INVALID_ARGUMENT")
```

```bash
python -m unittest tests.test_plan_execution.ToolContractTests.test_learning_invalid_search_arguments -v
```

## L1-03：适用条件矩阵

位置为 [tests/test_knowledge_platform.py](../../tests/test_knowledge_platform.py) 的 `RetrievalTests`。缺少商品时先澄清，明确为商品 B 时没有适用证据，完整匹配时允许引用。原 `test_invented_quote_rejected` 单独检查伪造引文。

```python
def test_learning_scope_matrix(self):
    rid = self.publish(
        [self.ingest(regions=["上海"], channels=["app"], products=["A"])]
    )
    retriever = HybridRetrieval(self.config)
    cases = (
        ({}, "needs_clarification"),
        ({"region": "上海", "channel": "app"}, "needs_clarification"),
        ({"region": "上海", "channel": "app", "product": "B"}, "no_evidence"),
        ({"region": "上海", "channel": "app", "product": "A"}, "answerable"),
    )
    for context, expected in cases:
        with self.subTest(context=context):
            result = retriever.search("七天退货", context=context)
            self.assertEqual(result["outcome"], expected)
            if expected == "answerable":
                self.assertEqual(result["citations"][0]["release_id"], rid)
                self.assertTrue(
                    retriever.validate_citations(rid, result["citations"])["valid"]
                )
```

```bash
python -m unittest tests.test_knowledge_platform.RetrievalTests.test_learning_scope_matrix -v
```

## L2-01：旧修订不能覆盖新内容

位置为 [tests/test_after_sale_intake.py](../../tests/test_after_sale_intake.py) 的 `IntakeTests`。`fill()` 从修订 0 写到修订 1；新命令即使换了幂等键也必须满足修订条件。冲突后正确做法是读取新状态再明确提交。

```python
def test_learning_stale_revision_does_not_overwrite(self):
    first = self.fill()
    with self.assertRaisesRegex(PlatformError, "INTAKE_VERSION_CONFLICT"):
        self.flow.command(self.identity, "update", 0, "stale", {"reason": "改为换货"})
    unchanged = self.flow.get(self.identity)
    self.assertEqual(unchanged["revision"], 1)
    self.assertEqual(unchanged["fields"]["reason"], first["fields"]["reason"])
    self.assertEqual(len(self.flow.history(self.identity)), 1)
    updated = self.flow.command(
        self.identity, "update", 1, "fresh", {"reason": "改为换货"}
    )
    self.assertEqual(updated["revision"], 2)
    self.assertEqual(updated["fields"]["reason"], "改为换货")
```

```bash
python -m unittest tests.test_after_sale_intake.IntakeTests.test_learning_stale_revision_does_not_overwrite -v
```

## L2-02：先确认，再重放结果

位置为 [tests/test_trusted_actions.py](../../tests/test_trusted_actions.py) 的 `TrustedActionsTests`。关键是确认前零工单，确认后多次请求仍只有一个结果。原 `test_model_claim_is_proposal_not_execution_and_registry_cannot_bypass` 还覆盖模型伪造的确认字段。

```python
def test_learning_pending_then_three_replays(self):
    action = self.propose()
    pending = self.invoke(action_id=action["action_id"])
    self.assertFalse(pending["success"])
    self.assertEqual(self.count(), 0)
    self.confirm(action)
    results = [self.invoke(action_id=action["action_id"]) for _ in range(3)]
    self.assertTrue(all(result["success"] for result in results))
    self.assertEqual(len({result["case"]["case_id"] for result in results}), 1)
    self.assertTrue(all(result["idempotent_replay"] for result in results[1:]))
    self.assertEqual(self.count(), 1)
    self.assertEqual(self.count(action_confirmations_table), 1)
```

```bash
python -m unittest tests.test_trusted_actions.TrustedActionsTests.test_learning_pending_then_three_replays -v
```

## L2-03：人工消息受当前所有权约束

位置为 [tests/test_platform_governance.py](../../tests/test_platform_governance.py) 的 `ConversationHandoffTests`。接管与释放都带预期所有权版本。同键同内容是重放，同键不同内容是冲突，释放后不能再作为当前客服回复。

```python
def test_learning_human_reply_requires_current_owner(self):
    self.collab.transition("u", "u:s", "a", 1, take=True)
    first = self.collab.message("u", "u:s", "a", "人工答复", "same")
    self.assertEqual(first, self.collab.message("u", "u:s", "a", "人工答复", "same"))
    with self.assertRaises(PlatformError):
        self.collab.message("u", "u:s", "a", "不同内容", "same")
    self.collab.transition("u", "u:s", "a", 2, take=False)
    with self.assertRaises(PlatformError):
        self.collab.message("u", "u:s", "a", "释放后回复", "new")
    self.assertEqual(len(self.collab.messages("u", "u:s")), 1)
```

```bash
python -m unittest tests.test_platform_governance.ConversationHandoffTests.test_learning_human_reply_requires_current_owner -v
```

## L3-01：新所有者复用已完成记录

位置为 [tests/test_async_runs.py](../../tests/test_async_runs.py) 的 `AsyncRunTests`。`expire()` 只修改当前 fixture 的临时租约，模拟中断恢复，不要求实际等待。第二个调用的函数不会执行，结果来自已完成调用记录。未知结果场景须另看原 `test_inflight_write_goes_to_reconciliation_and_cannot_replay`。

```python
def test_learning_fenced_owner_and_completed_replay(self):
    context = self.context()
    effects = []
    with context:
        first = context.call(
            "write", "refund", {}, lambda: effects.append("once") or '{"success":true}'
        )
    self.expire(context.run_id)
    fresh = self.repo.claim("worker-b")
    self.assertIsNotNone(fresh)
    with self.assertRaises(RunInterrupted):
        context.check()
    with RunContext(self.repo, fresh) as recovered:
        replay = recovered.call(
            "write", "refund", {}, lambda: effects.append("duplicate")
        )
    self.assertEqual(replay, first)
    self.assertEqual(effects, ["once"])
```

```bash
python -m unittest tests.test_async_runs.AsyncRunTests.test_learning_fenced_owner_and_completed_replay -v
```

## L3-02：金额差一分也不能结案

位置为 [tests/test_external_refund_recovery.py](../../tests/test_external_refund_recovery.py) 的 `ExternalRefundTests`。回执核对检查明确终态和绑定字段；只读到一个退款编号或 `success` 标记仍不足够。`ready` 表示可以进入有凭证的人工核对流程，并未自动替管理员完成结案。

```python
def test_learning_amount_mismatch_then_valid_receipt(self):
    reconciliation, rid = self.execute_in_run()
    for receipt in (
        self.receipt | {"amount_cents": self.receipt["amount_cents"] + 1},
        self.receipt | {"status": "processing"},
    ):
        self.adapter.receipt = receipt
        result = self.cases.recover_case(self.case_id)
        self.assertEqual(result["operation"]["status"], "unknown")
        self.assertFalse(reconciliation.inspect(rid)["ready"])
    self.adapter.receipt = self.receipt
    self.assertTrue(self.cases.recover_case(self.case_id)["success"])
    self.assertTrue(reconciliation.inspect(rid)["ready"])
    self.assertEqual(self.adapter.submissions, [self.key])
    self.assertEqual(self.adapter.lookups, [self.key] * 3)
```

```bash
python -m unittest tests.test_external_refund_recovery.ExternalRefundTests.test_learning_amount_mismatch_then_valid_receipt -v
```

## L3-03：摘要不能伪造原件结论

位置为 [tests/test_agent_quality_cli.py](../../tests/test_agent_quality_cli.py) 的 `QualityTests`。此处最小报告只验证序列化完整性，根本不具有配置发布资格。正式门禁还需检查数据、完整矩阵、配置和知识快照、逐条事实与引用；原 `test_two_batches_publish_the_pinned_release_without_touching_knowledge_head` 覆盖整个受控 CLI 流程。

```python
def test_learning_summary_tamper_is_rejected(self):
    from app.platform.evaluation_artifacts import write_report

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "report.json"
        report = {"agents": {"passed": False, "cases": []}}
        write_report(path, report)
        self.assertEqual(load_report(path), report)
        summary = json.loads(path.read_text())
        summary["agents"]["passed"] = True
        path.write_text(json.dumps(summary))
        with self.assertRaisesRegex(PlatformError, "EVALUATION_ARTIFACT_INVALID"):
            load_report(path)
```

```bash
python -m unittest tests.test_agent_quality_cli.QualityTests.test_learning_summary_tamper_is_rejected -v
```

## 讲解核对表

| 常见说法 | 合格解释 |
|---|---|
| “测试回复正确，模型就能回答所有问题” | 受控输入只验证已覆盖的程序路径，真实质量需要人工审核和独立评测 |
| “找到一条政策就能承诺退款” | 还要检查适用性、时间、冲突、引用和业务条件 |
| “有幂等键，超时就可以一直重试” | 已完成结果可重放，未知副作用先按原键查询并核对终态 |
| “客服接管后，之前的外部调用一定取消” | 阻止新的自动调用不等于撤销已发出的在途请求 |
| “报告哈希正确，所以可以发布” | 完整性、评分、审核来源和实际目标快照是不同的检查 |
| “临时测试账号批准了，所以人工审核完成” | 自动 fixture 只验证门禁分支，不计入原 32 题真实审核进度 |
