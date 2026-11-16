# 第一层：模型、工具与政策证据

[课程路线](README.md) · [环境准备](setup.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

先完成环境准备。这一层用测试替身固定模型输出，观察真实应用代码怎样处理消息、工具参数和知识引用。每个实验的“基线验证”现在即可执行；作业中的新方法由学员加入后再验证，答案集中在[参考答案](solutions.md)。

## L1-01：替换模型，保持应用行为可测试

**问题与目标。** 客户发送“你好”时，怎样在没有真实模型密钥的情况下检查回复结构和会话保存？学会从应用工厂注入配置与模型客户端，区分原始模型消息、结构化响应和持久化消息。

**前置。** Python 类、上下文管理器、unittest 断言。

**代码入口。** [应用装配](../../app/bootstrap.py)的 `create_agent`、[EcomAgent](../../app/agent/chat.py)、[响应模型](../../app/schemas/response.py)、[工厂测试](../../tests/test_architecture.py)的 `ApplicationFactoryTests` 与 `FakeOpenAI`。

**基线验证。**

```bash
python -m unittest tests.test_architecture.ApplicationFactoryTests -v
python -m unittest tests.test_async_runs.AsyncRunTests.test_real_react_agent_and_gateway_run_offline -v
```

观察工厂测试怎样断言同一配置与客户端被注入，回复满足 `CustomerServiceResponse`，会话文件实际存在。第二条通过离线网关运行真实 ReAct 路径。测试通过说明这条程序路径可复现，不是模型对陌生输入的理解能力得分。

**动手作业。** 在 `ApplicationFactoryTests` 中新增 `test_learning_injected_reply`。让模型替身的结构化回复变成“欢迎进入售后实验”、置信度为 `0.42`，使用临时数据库和会话路径，断言应用返回相同字段且会话已保存。画出 `create_agent → chat → 模型网关 → 结构化响应 → save` 的调用顺序，并解释 `0.42` 为什么只是 fixture 数据。

**交付与验收。** 提交测试 diff、实际执行记录和调用图；故意把预期回复改成其他文字时，新增断言应失败。参考答案给出完整测试方法与单独执行命令。

## L1-02：工具参数和远端身份从哪里来

**问题与目标。** 模型给出一个工具名和 JSON 参数，能否直接执行？学会识别可见 schema、服务端参数校验、工具权限和 MCP 身份签名的不同职责。

**前置。** L1-01，JSON 对象与必填字段。

**代码入口。** [工具参数模型](../../app/agent/tools/contracts.py)、[工具注册与执行](../../app/agent/tools/registry.py)、[MCP 治理](../../app/platform/connectors.py)，以及 [ToolContractTests](../../tests/test_plan_execution.py) 和 [ConnectorTests](../../tests/test_platform_governance.py)。

**基线验证。**

```bash
python -m unittest tests.test_plan_execution.ToolContractTests -v
python -m unittest tests.test_platform_governance.ConnectorTests.test_signed_identity_wrong_tenant_permission_and_expiry tests.test_platform_governance.ConnectorTests.test_override_and_unapproved_write_rejected -v
```

工具缺必填项、传额外字段或超出参数范围时，应在处理器前返回 `INVALID_ARGUMENT`。MCP 令牌测试使用固定时间，错误租户、权限与过期令牌均被拒绝；第二个 MCP 用例使用 Mock 客户端，不连接远端服务。

**动手作业。** 在 `ToolContractTests` 新增 `test_learning_invalid_search_arguments`，覆盖缺 `query`、`top_k=0`、模型额外传入 `user_id` 三组输入，每组均断言 `INVALID_ARGUMENT`。补一张表说明“参数合法”“有读取权限”“用户已确认写操作”分别由哪一层检查。

**交付与验收。** 三个负例的测试 diff 和错误码记录；说明把 `user_id` 写进模型参数不能作为经过验证的身份。真实 MCP 传输由演示启动器和已有 HTTP 测试覆盖，本实验只验证参数与治理规则。

## L1-03：检索命中以后，政策是否真的适用

**问题与目标。** 找到了“七天退货”，但政策只适用于上海、App 和商品 A，信息不全时能否给出承诺？学会检查适用范围、知识版本和引用位置。

**前置。** L1-02，知道文档切分和 Top-K 的基本含义。

**代码入口。** [知识导入与版本](../../app/platform/knowledge.py)、[检索与引用验证](../../app/platform/retrieval.py)，[RetrievalTests](../../tests/test_knowledge_platform.py)、[政策冲突回归](../../tests/test_policy_context.py)。测试使用本地 `LocalHashEmbedder`，不调用外部 embedding。

**基线验证。**

```bash
python -m unittest tests.test_knowledge_platform.RetrievalTests.test_metadata_before_and_after_search tests.test_knowledge_platform.RetrievalTests.test_invented_quote_rejected -v
python -m unittest tests.test_policy_context.PolicyConflictTests.test_conflict_outside_candidate_pool_cannot_be_hidden_by_top_k -v
```

先预测缺范围、范围不符和完全匹配三种结果，再对照 `needs_clarification`、`no_evidence`、`answerable`。原文引用被改写时验证失败；即使 `top_k=1`，同政策的有效冲突也不能被展示截断隐藏。

**动手作业。** 在 `RetrievalTests` 新增 `test_learning_scope_matrix`，导入上海/App/商品 A 的政策，测试空条件、缺商品、商品 B 和完全匹配四组条件。完整匹配时还需验证引用属于实际发布版本。

**交付与验收。** 四行输入—结果矩阵、引用中的 `release_id/version_id/chunk_id` 含义和测试 diff。解释为什么本地哈希向量与规则重排不能证明真实语义检索效果。

下一步进入[业务流程层](level-2-workflows.md)。
