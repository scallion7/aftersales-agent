# 第三层：恢复、对账与评测发布

[课程路线](README.md) · [第二层](level-2-workflows.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

这一层以失败场景为起点，检查调用记录、数据库状态和报告原件。前置为第二层和基本 SQL 事务知识。主实验全部使用可丢弃数据；原人工审核材料、冻结保留集及真实模型保持不变。

## L3-01：旧 Worker 为什么不能继续提交

**问题与目标。** Worker A 领取任务后退出，Worker B 接管时，A 又恢复运行。怎样避免旧 Worker 覆盖新状态？学会解释租约、fencing、调用账本和已完成结果重放。

**代码入口。** [RunRepository](../../app/repositories/runs.py)、[RunContext](../../app/services/run_context.py)的 `check/call`、[RunWorker](../../app/services/runs.py)、[AsyncRunTests](../../tests/test_async_runs.py)。

**基线验证。**

```bash
python -m unittest tests.test_async_runs.AsyncRunTests.test_two_workers_only_one_claim tests.test_async_runs.AsyncRunTests.test_expired_worker_is_fenced_and_model_retry_is_recorded tests.test_async_runs.AsyncRunTests.test_completed_write_is_replayed_without_duplicate_effect tests.test_async_runs.AsyncRunTests.test_inflight_write_goes_to_reconciliation_and_cannot_replay -v
```

观察成功领取者只有一个、旧所有者检查失败、已记录完成的写调用直接重放，以及未确认终态的写调用进入 `needs_reconciliation`。模型调用中断后可能重测并产生重复费用风险，不能把“应用能恢复”解释为外部每一笔调用都恰好一次。

**动手作业。** 在 `AsyncRunTests` 新增 `test_learning_fenced_owner_and_completed_replay`。记录一次已完成的测试写操作，令租约到期并由另一个 Worker 领取；断言旧上下文被 fencing 阻止，新上下文重放相同调用时副作用列表仍只有一项。

**交付与验收。** 两个 Worker 的时间线、调用账本状态和新增测试。分别说明“已完成记录”“发出后结果未知”应选择重放结果还是对账。

## L3-02：退款超时以后，先查原请求

**问题与目标。** 供应商收到了退款请求，响应却丢失，能否换个请求号重发？学会用固定业务幂等键核对订单、用户、金额、退款号和终态回执。

**代码入口。** [外部 Provider](../../app/services/providers.py)、[退款回执契约](../../app/services/refund_contracts.py)、[售后服务](../../app/agent/after_sale/service.py)、[任务核对结案](../../app/services/run_reconciliation.py)、[外部退款恢复测试](../../tests/test_external_refund_recovery.py)。这里的 `external` 配置配合注入的本地 `Adapter` fixture 使用，不接真实供应商。

**基线验证。**

```bash
python -m unittest tests.test_external_refund_recovery.ExternalRefundTests.test_timeout_stays_blocked_until_bound_provider_receipt_after_restart tests.test_external_refund_recovery.ExternalRefundTests.test_crash_before_case_sync_resumes_from_stored_receipt -v
```

`Adapter.submit_refund` 记录一次提交后抛出超时，恢复代码只能查询原键。错误金额、其他订单、处理中和空回执都不能证明退款完成；匹配终态回执与业务状态才允许核对结案。第二条模拟回执保存后工单写入失败，重启从保存的回执恢复，不重复提交。

**动手作业。** 在 `ExternalRefundTests` 新增 `test_learning_amount_mismatch_then_valid_receipt`。先造成结果未知，返回金额多 1 分的回执、`processing` 回执和正确终态回执。前两次仍不可结案，最后一次可核对；总提交数保持 1，三次查询都使用原键。

**交付与验收。** 三种回执的判断表、新增测试和提交/查询次数。说明 `accepted` 与实际退款完成不同，人工结案也不能用无关联的文字说明替代绑定回执。

## L3-03：评测未完成或原件被修改时阻止发布

**问题与目标。** 一个报告写着“通过”，但只运行了一部分题目，或摘要与原件不一致，能否发布配置？学会固定知识和配置、分批续跑、重算回答证据与校验报告完整性。

**代码入口。** [评分规则](../../app/platform/agent_quality.py)、[报告原件](../../app/platform/evaluation_artifacts.py)、[评测隔离](../../app/platform/evaluation_workspace.py)、[配置发布](../../app/platform/releases.py)、[CLI 评测回归](../../tests/test_agent_quality_cli.py)。

**基线验证。**

```bash
python -m unittest tests.test_agent_quality_cli.QualityTests -v
```

四个测试覆盖事实与引用反例、审核与数据切分门禁、审核回执的来源绑定，以及真正调用 CLI 的两批评测到发布流程。最后一个测试使用两条合成 development 题和本机受控 HTTP 模型，第一批缺项时拒绝发布，续跑复用已完成格，最终仅激活临时库中的目标配置；源知识头始终不变。测试会自行启停回环模型进程。

审核门禁测试会在临时项目中生成合成审核账号和批准记录，部分输入用 `live` 字段覆盖校验分支。这些数据不是人工审核记录，没有连接真实模型，也没有运行原 16 题保留集。

**动手作业。** 在 `QualityTests` 新增 `test_learning_summary_tamper_is_rejected`。在临时目录写一份最小失败报告，确认能完整读取；仅把摘要中的 `passed` 改为 `true`，保留压缩原件与 SHA-256 指针，断言 `load_report` 拒绝读取。解释“原件哈希正确”为什么仍不足以证明摘要真实，更不足以证明回答正确。

**交付与验收。** 新增测试、两批评测状态图和三个发布阻断条件。评分采用保守原文支持规则，不等同于语义蕴含判断。正式 CLI 参数见[评测发布协议](../evaluation/offline-review.md)，本课程不把测试报告导入业务库，也不运行 `--live` 真实评测。

## 扩展实践

备份和日志并发可阅读[恢复与文件输出测试](../../tests/test_maintenance_outputs.py)及 [SQLite 快照测试](../../tests/test_sqlite_snapshots.py)；风险阈值固定见[对应回归](../../tests/test_pinned_risk_limits.py)。需要完整部署验证时，按[Compose 验收](../operations/compose-acceptance.md)新建可丢弃环境。完成主实验后按[结课任务](README.md)交付自己的演示和报告。
