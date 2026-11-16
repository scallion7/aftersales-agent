# 第二层：从对话到业务状态

[课程路线](README.md) · [第一层](level-1-foundations.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

这一层沿着“补材料 → 提案 → 确认 → 工单 → 人工协作”理解业务流程。先完成第一层；测试使用临时 SQLite、合成订单和模型替身。参考答案中的作业方法需要学员先加入指定测试类。

## L2-01：多轮申请和修订冲突

**问题与目标。** 客户先补订单，再补原因，随后在另一页面修改诉求，旧页面能否覆盖新内容？学会追踪申请的 `revision`、字段来源、命令幂等键与旧提案失效。

**前置。** L1-01～03，了解数据库持久化和乐观并发控制的基本概念。

**代码入口。** [AfterSaleIntake](../../app/platform/after_sale_intake.py)的 `create/command/get/history`、[对话申请工具](../../app/agent/tools/intake.py)、[申请回归](../../tests/test_after_sale_intake.py)。

**基线验证。**

```bash
python -m unittest tests.test_after_sale_intake.IntakeTests.test_missing_fields_survive_restart_and_user_scope tests.test_after_sale_intake.IntakeTests.test_modify_invalidates_confirmed_action_and_reconfirmation_required -v
```

资料不全时不能生成提案；重新实例化服务仍能读取已补字段。修改诉求后旧确认失效，撤回申请会阻止继续写入。状态变化必须同时考虑 `revision` 和 `action_id`，单看聊天记录不足以判断能否执行。

**动手作业。** 在 `IntakeTests` 新增 `test_learning_stale_revision_does_not_overwrite`。先补齐资料到修订 1，再用修订 0 和新命令键修改原因，预期 `INTAKE_VERSION_CONFLICT`；验证字段、修订和历史条数未改变。最后用修订 1 重试新命令，预期保存为修订 2。

**交付与验收。** 绘制两客户端读写时序图，记录冲突前后字段值和历史条数。选做真实 HTTP 对话路径如下，该测试会自行启停本机 API 与 Worker，并验证重启、改诉求、确认及撤回。

```bash
python -m unittest tests.test_dialogue_intake.DialogueIntakeTests.test_partial_change_proposal_restart_and_no_automatic_case -v
```

## L2-02：确认绑定具体操作，重复执行不重复创建

**问题与目标。** 模型说“用户已经确认”与用户点击具体操作的确认按钮有什么区别？学会追踪提案、身份、参数摘要、业务版本及一次性确认。

**前置。** L2-01，L1-02 的工具参数检查。

**代码入口。** [ActionService](../../app/services/actions.py)、[统一工具执行](../../app/services/tool_execution.py)、[TrustedActionsTests](../../tests/test_trusted_actions.py)的 `propose/confirm/invoke/count` fixture。

**基线验证。**

```bash
python -m unittest tests.test_trusted_actions.TrustedActionsTests.test_model_claim_is_proposal_not_execution_and_registry_cannot_bypass tests.test_trusted_actions.TrustedActionsTests.test_confirm_then_execute_and_repeat_replays_once tests.test_trusted_actions.TrustedActionsTests.test_other_user_and_session_cannot_confirm -v
```

模型提供的确认字段不会创建业务记录。经过服务器确认后，执行并重放应返回同一 `case_id`，工单与确认记录各一条；另一用户或会话无法确认这份提案。

**动手作业。** 在 `TrustedActionsTests` 新增 `test_learning_pending_then_three_replays`。先尝试执行未确认提案，断言没有工单；确认后执行三次，断言只有一条工单、一条确认，三次返回相同工单号，后两次标明 `idempotent_replay`。

**交付与验收。** 提交测试 diff 和“未确认/已确认/执行完成/重放”的状态表。明确这个实验创建的是本地测试工单，不能把它描述为真实支付系统的恰好一次退款保证。

## L2-03：策略分工和人工接管

**问题与目标。** 多 Agent 路由到售前角色后，能否调用售后订单工具？客服接管时，怎样避免自动回复继续发送或人工消息重复写入？学会区分策略选择、工具范围与会话所有权。

**前置。** L2-02，理解 ReAct 的逐步选择和 Plan-and-Execute 的计划依赖。

**代码入口。** [计划执行器](../../app/agent/strategies/executor.py)、[多 Agent 编排](../../app/multi_agent/orchestrator.py)、[人工接管服务](../../app/platform/conversation_handoff.py)、[Worker 完成事务](../../app/services/runs.py)。

**基线验证。**

```bash
python -m unittest tests.test_plan_execution.MultiAgentStrategyTests.test_routed_agent_executes_plan_with_its_tool_scope tests.test_plan_execution.MultiAgentStrategyTests.test_plan_cannot_use_tool_outside_routed_agent_scope -v
python -m unittest tests.test_handoff_execution.HandoffExecutionTests.test_take_release_invalidates_old_run_new_request_executes tests.test_platform_governance.ConversationHandoffTests.test_human_message_idempotency_and_conflict -v
```

合法计划按依赖调用订单和物流工具。越过角色范围的计划被拒绝并回退，不产生那些工具调用。接管后再释放不恢复旧任务意图，新的用户请求才能继续执行；相同人工消息请求只保留一份。

**动手作业。** 在 `ConversationHandoffTests` 新增 `test_learning_human_reply_requires_current_owner`。客服接管后，重复发送同键同内容返回同一结果，同键不同内容被拒绝；释放后再发送新人工消息也应被拒绝。记录人工消息最终只有一条。

**交付与验收。** 一张“策略—角色工具范围—会话所有权”职责表，新增测试和一次操作记录。说明接管会阻止新的自动调用，但已经发往外部的在途请求不能假定被撤销。参考[人工接管边界](../engineering/human-handoff.md)。

下一步进入[可靠执行层](level-3-reliability.md)。
