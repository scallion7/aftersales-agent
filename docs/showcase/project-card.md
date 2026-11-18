# AfterSales Agent 项目卡

[展示材料](README.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

## 项目定位

**AfterSales Agent｜面向电商售后的可恢复智能体平台**

面向订单咨询、政策问答与售后办理，将多轮申请、政策证据、具体操作确认、持久化任务、退款对账和人工接管连接成完整业务流程。模型负责理解、规划与解释，服务端负责身份、授权、业务规则、状态和审计。

维护者为 [scallion7](https://github.com/scallion7)。项目从电商客服原型持续扩展，设计和提交依据见[工程演进](../CONTRIBUTIONS.md)。展示定位为 Agent 应用工程，适合讨论可靠业务执行、评测治理和交付验证。

当前范围为系统搭建、技术探索与受控工程验证。人工审核、真实模型效果评测和生产环境验证列为**后续自费验证，当前项目范围外**，详见[项目范围](../evaluation/acceptance.md#project-scope)。

## 一个具体例子

用户说“这件衣服尺寸不合适，想退货”。系统查询属于该用户的订单和适用政策，追问缺失信息并保存申请草稿。生成提案后，用户核对订单、原因和诉求再确认。服务端根据当时的业务版本创建工单，必要时进入审批；后续退款使用独立的执行授权。若供应商已受理但响应丢失，系统保留原业务键进入查单，避免因网络重试重复提交资金操作。

## 系统组成

| 范围 | 实现 |
|---|---|
| 用户与客服 | 客户工作区、售后表单、客服工作台、评测复核工作台 |
| Agent | ReAct、Plan-and-Execute、多 Agent 路由、统一工具执行与 MCP 接入 |
| 知识 | 政策适用条件、版本化快照、BM25/余弦/RRF、稳定原文引用与冲突检查 |
| 执行 | SQL 持久化任务、租约与 fencing、幂等、Outbox/Inbox、退款对账 |
| 治理 | OIDC 身份隔离、用户确认、人工审批与接管、配置与风险阈值固定 |
| 验证 | 回归测试、真实 HTTP/MCP 和浏览器交互、数据库迁移、故障演练、评测发布门禁 |

技术栈包括 Python、FastAPI、Pydantic、SQLAlchemy/Alembic、SQLite/PostgreSQL、MCP Streamable HTTP、OpenTelemetry、Playwright、Docker Compose 和 GitHub Actions。模块与调用关系见[系统架构](../architecture/overview.md)。

## 问题、设计与证据

| 具体问题 | 核心设计 | 代码与回归依据 |
|---|---|---|
| 模型声称“用户已确认”，能否直接执行退款？ | 服务端提案绑定身份、会话、参数和业务版本，显式确认后重新校验并领取 | [工具执行](../../app/services/tool_execution.py)、[可信确认测试](../../tests/test_trusted_actions.py) |
| 用户补资料后又改诉求，旧确认是否仍有效？ | 持久化申请修订、来源与命令回执，修改或撤回使旧授权失效 | [申请服务](../../app/platform/after_sale_intake.py)、[多轮申请测试](../../tests/test_dialogue_intake.py) |
| Worker 退出后，旧进程还能提交结果吗？ | 领取租约、递增 fence、提交时检查所有权及版本 | [任务仓储](../../app/repositories/runs.py)、[异步任务测试](../../tests/test_async_runs.py) |
| 退款超时能否换请求键再试？ | 先保存稳定业务键，未知结果只查原键，核对供应商终态及绑定回执 | [退款工作流](../../app/services/refund_workflow.py)、[外部退款恢复测试](../../tests/test_external_refund_recovery.py) |
| 客服接管后，自动回复或下一次工具调用会不会继续？ | 调用登记与最终回复检查所有权版本，交接输入、事件和终态同事务提交 | [接管服务](../../app/platform/conversation_handoff.py)、[交接竞争测试](../../tests/test_handoff_execution.py) |
| 浏览器丢失回执且令牌续签，是否会重复发消息？ | 未决请求绑定已认证主体，续签后复用原键；不同主体隔离 | [请求客户端](../../app/web/request_client.js)、[浏览器重试测试](../../tests/test_browser_retries.py) |
| 旧会话会不会突然使用新的审批金额阈值？ | 新配置快照固定阈值并参与哈希，旧版本缺少阈值时保守转人工 | [发布与阈值](../../app/platform/releases.py)、[固定风险规则测试](../../tests/test_pinned_risk_limits.py) |
| 报告显示通过，原始回答却错误或报告不完整？ | 摘要关联带 SHA-256 的原件，发布时复算逐格事实、引用与完整性 | [原件校验](../../app/platform/evaluation_artifacts.py)、[评测发布测试](../../tests/test_agent_quality_cli.py) |

## 可引用的已有结果

| 已有记录 | 使用口径 |
|---|---|
| 2026-11-18 本地 554 项回归通过，无跳过 | Python 3.11、项目锁定依赖、启用 Chromium；包含单元、集成和浏览器测试 |
| 同次 app 语句覆盖率 84% | 沿用 coverage 配置，不包含 `app/scripts/*` 及独立进程；门禁下限为 65% |
| 2026-11-13 的 9 个开发家族 × 3 个策略共 27 格通过 | 使用受控 HTTP 模型，验证回答评分和配置发布流程；首次错误回复曾被门禁拦截 |
| 2026-11-13 的 18 项 HTTP 任务契约通过 | 检查工具调用及数据库终态，使用合成业务和 mock 商务 Provider |
| `e0271e8` 的 CI 为 9/9 作业成功 | 覆盖 Python 3.10–3.12、迁移、浏览器、供应链、Compose 和短时负载 |

原始摘要见[2026-11-18 本地复验](../evidence/aftersales-rename-20261118/checks.json)和[2026-11-13 受控评测清单](../evidence/release-workflow-20261113/checks.json)，远端状态见[固定提交的 CI](https://github.com/scallion7/aftersales-agent/actions/runs/44317537941)。这些是已有验证记录，文档修订不构成新的测试运行；不同日期、环境和测试集合的数字不可相加为项目总样本量。

## 演示与后续自费验证

现场从[五分钟操作指南](../guides/five-minute-demo.md)开始，完整展示安排见[演示材料](demo.md)。默认演示使用本地受控模型和合成数据，无需真实模型密钥或支付账户。

原 32 题真实人工审核尚未完成，原冻结 16 题保留集和真实模型评测未运行。若后续自费启动效果验证，应先完成审核，再按冻结协议分别记录质量、延迟和费用；生产接入另需实际环境和供应商联调。当前项目不包含这些外部验证，也不填写真实模型准确率、节省人力、线上业务收益或生产 SLA。条件与现状见[项目范围](../evaluation/acceptance.md#project-scope)。
