# 当前验收状态

[文档中心](../README.md) · [证据索引](../evidence/README.md)

<a id="project-scope"></a>

## 当前项目范围

当前项目以**系统搭建与技术挖掘**为目标，交付 Agent 策略与工具接入、政策检索、多轮业务流程、可信执行、任务恢复、评测发布机制，以及可复现的测试、演示和教学材料。验收使用合成业务、受控模型及隔离环境，实际运行 HTTP、MCP、Worker、数据库与浏览器，检查各模块的工程行为。

**人工审核、真实模型效果评测和生产环境验证统一标记为“后续自费验证，当前项目暂不涉及”。** 这些工作不列入当前项目交付待办；相关能力和指南保留，后续开展时另行安排审核人力、模型调用费用、部署资源与执行范围。此范围约定不改变历史事实：原 32 题未完成真实人工审核，原 16 题保留集未运行，真实模型质量与生产表现尚无验证结果。

审核工作台、生产发布门禁、供应商适配器等机制的实现与受控回归属于当前范围；真实审核、付费评测和生产联调的实际开展属于范围外。范围调整不放宽已有审核与发布条件，也不把受控测试结果转换为模型准确率或业务收益。下面各日期的验收记录保留当时环境与结果；范围外事项集中列于文末的后续自费验证清单。

<a id="agent-boundaries-20261118"></a>

## 2026-11-18 换货、政策问答与会话恢复

| 场景 | 修复后的行为 | 验证入口 |
|---|---|---|
| 换货与历史退款 | 新换货转人工审核，客服登记履约凭证后结案。可证实从未发送的旧退款指令会取消，可能已发送的按原业务键查单。 | [操作步骤与状态](../guides/after-sale.md)、[退款分发回归](../../tests/test_refund_delivery.py) |
| 政策问答 | 启用版本化知识库时，缺少本轮可信证据的政策问答提示人工核实。重放检索时校验引用，会话历史和短期记忆只记录用户最终看到的答复。 | [客户回合回归](../../tests/test_customer_turn_finalization.py) |
| 会话恢复 | 切换账号或会话时清空原页面，迟到的响应按发起时的身份和会话校验。刷新后点击“连接会话”即可恢复当前会话仍保留的消息，并可继续同一项已确认操作。旧提案保留在操作卡中，后续无关问题可以正常回答。记忆更新暂时失败时，最近八轮问答可在恢复后补写。 | [会话隔离回归](../../tests/test_workspace_scope.py)、[确认后恢复回归](../../tests/test_browser_retries.py) |
| 任务、风控与退款原因 | 同步聊天等待已被 Worker 领取的原任务，等待超时可用响应中的 `Location` 继续查询。SQLite 和 PostgreSQL 将规则激活与回滚串行执行，回滚选择最近退役的版本。浏览器和 HTTP 退款接口均接受最长 1000 字符的原因。 | [超时配置](../guides/configuration.md)、[风控回归](../../tests/test_provider_and_policy_governance.py)、[退款契约](../../tests/test_refund_delivery.py) |

本轮在 Python 3.11.15 上启用 Chromium，**526 项测试通过，零跳过**，用时 116.547 秒，app 语句覆盖率为 **83%**。Ruff、格式和 104 条 OpenAPI 路径检查通过，离线计划质量门禁 40/40 通过。[本地验证清单](../evidence/agent-boundaries-20261118/checks.json) · [逐项测试结果](../evidence/agent-boundaries-20261118/unittest-results.log.gz) · [覆盖率明细](../evidence/agent-boundaries-20261118/coverage.log)

在 PostgreSQL 17.11 的隔离实例上，发布与回滚同时等待写锁时，修复前留下两个活动版本，修复后只剩一个。同一任务由 8 个 Worker 争抢，只有 1 个成功领取。两类历史换货处理均未发起新的供应商退款，普通退款的 10 次回调只应用 1 次。[数据库结果](../evidence/agent-boundaries-20261118/postgres.json)

在同一批 16 道合成开发题上，混合检索在 14 道有预期文档的题目上均召回了全部标注候选。最终返回了标注证据的题目由 6/14 增至 11/14，证据状态判对由 8/16 增至 13/16，仍有三道题被过度拒答。比较使用本地哈希向量和未经人工复核的开发题，保留集和真实模型未参与。[检索实验与逐项对比](retrieval-experiments.md)

## 2026-11-16 依赖安全补丁复验

展示材料提交 `e7e1eed` 的 [CI 43850705491](https://github.com/scallion7/xc_sx_agent/actions/runs/43850705491) 在精确依赖审计中发现 `opentelemetry-api 1.45.1` 的 CVE-2026-126360，因此该次运行不能记为全绿。按[上游公告](https://github.com/open-telemetry/opentelemetry-python/security/advisories/GHSA-mf5v-w3w3-f6cg)，将 API/SDK 同步锁定到 `1.45.2`、semantic-conventions 到 `0.66b2`，同时提高 SDK 支持范围的安全下限。其他锁定版本保持不变。

更新后的本地环境逐项匹配 58 个锁定包，`pip check` 通过。两份依赖审计分别覆盖 58/53 个包，均未发现已知漏洞。再次启用 Chromium 运行完整回归，**500 项通过、无跳过，108.695 秒，app 语句覆盖率 82%**。审计 JSON、完整回归压缩日志、覆盖率及锁文件哈希见[补丁复验清单](../evidence/dependency-patch-20261116/checks.json)。这次复验使用受控服务，没有开展真实模型或原冻结保留集评测；后续 CI 按[工作流](https://github.com/scallion7/xc_sx_agent/actions/workflows/offline-quality.yml)中的提交 SHA 核对。

## 2026-11-16 展示材料与分层教学

以代码基线 `37e2fd7` 整理[简历与面试材料](../showcase/README.md)、[三项演示](../showcase/demo.md)和[分层实验](../learning/README.md)。本批未修改应用或现有测试源码，原阶段记录及冻结数据保持原样。

重新运行本地 Python 3.11 回归，启用项目锁定的 Chromium，**500 项通过、无跳过，112.378 秒**；app 语句覆盖率 **82%**，沿用既有排除范围。另实际验证浏览器录制、退款未知恢复、两批评测与拒绝发布、`demo_stack --intake --smoke`，并通过 Ruff、格式、编译和 104 路径的 OpenAPI 检查。单独演示检查是既有用例的再次运行，不与 500 项相加为新测试总数。

教学中的 14 条基线命令共 31 项测试最终通过；九个参考方法从文档代码块加载到对应测试类，**9/9 通过**，未加入仓库原有测试集合。文档命令、代码片段和本地链接均完成检查。复录工具另验证已有目录拒绝覆盖和非法间隔参数拒绝，视频参数与实际播放尺寸单独核对。

客户与客服的两段无配音录像、两张截图、退款 HTTP 轨迹、检查结果及 SHA-256 见[本批证据](../evidence/showcase-20261116/checks.json)。录像使用受控模型和合成数据，展示范围及复录步骤见[素材说明](../showcase/recording.md)。本批不重新测量 PostgreSQL 持续负载或生产性能；推送后的多版本、数据库、容器与浏览器验证按[工作流](https://github.com/scallion7/xc_sx_agent/actions/workflows/offline-quality.yml)中对应提交 SHA 查阅。

原 32 题真实人工审核尚未完成，原 16 题保留集和真实模型评测未开展；这些工作归入[当前项目范围](#project-scope)之外的后续自费验证。课程中的自动化审核 fixture 和演示数据不计入真实审核进度，本批付费模型调用为 0。

## 2026-11-13 可靠性、政策评分与配置发布

本地 Python 3.11 启用 Chromium 后，500 项回归全部通过，无跳过，app 语句覆盖率 82%。SQLite 和 PostgreSQL 的升级、漂移检查、业务烟测及降级重建通过。PostgreSQL 短时负载完成 150/150 个任务，四项故障演练通过。

在隔离测试库中完成从目标草稿、固定知识快照、分批评测、报告校验到激活配置的验收。9 个开发家族 × 3 个 Agent 策略共 27 格，核对实际模型回复、检索日期与条件、逐条原文引用、关键事实和数据库终态。任务契约集另有 18 项 HTTP 验收。检查结果与来源环境见[本地检查清单](../evidence/release-workflow-20261113/checks.json)和[27 格评测报告](../evidence/release-workflow-20261113/evaluation.json)。

首次全矩阵检查中，计划执行策略的 5 个可回答题得到通用问候，评分阻止发布。受控模型接入实际计划步骤中的检索输出后，三个策略各通过 9/9，验证库已激活受评草稿。真实模型生产验收使用单独的审核导出、保留集和调用记录。当前原 32 题人工审核尚未完成，原 16 题保留集未运行，本地受控验证的付费调用数为 0。复现方式见[评测发布协议](offline-review.md)。

## 2026-11-10 历史基线

核验日期：2026-11-10。已归档的功能修复 CI 基线为 [`c5aee67`](https://github.com/scallion7/xc_sx_agent/commit/c5aee6716723ae5a4243497db919e094d3b238a5)，对应 [Actions 42813941711](https://github.com/scallion7/xc_sx_agent/actions/runs/42813941711) **9/9 作业成功**；结构化快照见 [ci.json](../evidence/boundary-fixes-20261110/ci.json)。固定提交的 CI、文档修订本地验收和历史性能测量分别列出，不合并不同环境或代码版本的数字。后续提交的状态查看 [Actions 工作流](https://github.com/scallion7/xc_sx_agent/actions/workflows/offline-quality.yml)，并按提交 SHA 核对。

## 功能修复基线的 CI

| 范围 | 验证结果与口径 |
|---|---|
| Python 3.10 / 3.11 / 3.12 | 每个版本发现 **468 项测试**，实际执行 **459 项通过、9 项浏览器测试跳过**；三个版本均成功 |
| 浏览器与 HTTP 专项 | 独立 `platform-browser` 作业设置 `RUN_BROWSER_E2E=1`，**18 项通过**，包含 9 项浏览器与 9 项 HTTP 测试；其中部分 HTTP 用例也在 Python 矩阵中，不重复累加为独立测试总数 |
| app 语句覆盖率 | Python 矩阵为 **83%**；不含 `app/scripts/*` 及独立进程，配置中的门禁下限仍为 65% |
| SQLite / PostgreSQL | 两个迁移作业通过空库升级、schema drift、业务/平台 smoke、降级与重新升级；使用独立测试数据 |
| 供应链与镜像 | 依赖范围和锁文件审计、SBOM、Docker 构建与 Trivy 门禁通过；镜像检查按工作流配置处理 HIGH/CRITICAL 及可修复问题，不表示软件绝无漏洞 |
| 完整部署与恢复 | `compose-acceptance` 通过隔离 Compose 部署及恢复验收，与本机原生 PostgreSQL 检查分别计证据 |
| PostgreSQL 短时负载 | CI 配置为 15 秒、10 次请求/秒、2 worker、队列上限 12，检查负载与故障契约；同时验证 1000 个合成 chunk 的预编译索引结果一致性 |
| 静态与工程门禁 | Ruff、格式、compileall、OpenAPI、文档链接、40 项计划质量门禁与计划基准通过 |

`platform-acceptance`、`compose-deployment-evidence`、`sustained-postgres-evidence` 和 `dependency-sbom` 产物从对应运行页面获取，受 Actions 保存期限约束。工作流通过不等于旧本地报告中的性能数字已在当前 CI 重现。

当前代码已覆盖 OIDC 以 issuer/sub 绑定身份、SQLite WAL 一致备份、返回 K 之外的同键政策冲突、未知副作用的人工核对结案、多轮政策条件来源与订单隔离、失效提案重新确认，以及页面遇到 409/未知回执的恢复处理。`c5aee67` 另补客服工作台操作至刷新完成期间的全局 busy 保护与浏览器回归。

## 文档修订的本地复核

2026-11-10 在以 `c5aee67` 为基线的未提交文档工作树中再次运行完整回归：设置 `RUN_BROWSER_E2E=1` 并使用已安装的 Chromium，**468 项通过、无跳过，95.859 秒**。另检查 6 个离线技能 helper、119 个环境配置键、文档 CLI 模块、103 个 OpenAPI 路径、364 个 Python 文件的 Ruff 检查及 `demo_stack --intake --smoke`。具体命令、检查结果和最后文档链接统计见[文档修订检查清单](../evidence/docs-refresh-20261110/checks.json)。这批本地复核没有重新测量覆盖率；上方 83% 来自 `c5aee67` 的 CI。

## 提交前的本地验收

[本地检查清单](../evidence/boundary-fixes-20261110/checks.json)记录基于 `2526710` 的未提交源码副本，保留当时的代码哈希、环境与未运行项目。以下 **467 项**早于新增工作台 busy 回归，不是当前提交的测试总数。

- **467 项回归通过，无跳过；103.184 秒**，使用 Python 3.11 与项目锁定的 Playwright Chromium；[完整日志](../evidence/boundary-fixes-20261110/unittest.log)。较修复前增加 39 项回归，另包含故障、并发和不同输入的子场景。
- **app 语句覆盖率 83%**；[覆盖率报告](../evidence/boundary-fixes-20261110/coverage.log)。脚本与独立进程沿用既有排除口径。
- SQLite/PostgreSQL 升级、schema drift、业务与平台烟测、降级重建通过；新增人工结案烟测在两种数据库验证四名管理员并发只有一次结案，并清理自身测试数据。PostgreSQL 停写备份恢复的数据指纹一致。
- 隔离 PostgreSQL 的 15 秒短时验证完成 150/150 个受控任务；容量拒绝、worker 退出、数据库停启和模型 HTTP 中断恢复通过。1000/10000 个合成 chunk 的索引结果一致。18 项受控任务、开发集检索比较、平台容量和故障脚本完成，无付费模型调用。
- Ruff、格式、compileall、OpenAPI、文档链接、40 项计划门禁及计划基准通过。两份依赖清单分别审计 58/53 个包，未发现已知漏洞。
- 该次本机没有 Docker 和 Python 3.10/3.12，因此原报告保留未运行容器构建/镜像扫描/Compose 及另外两个 Python 版本的记录。上方当前 CI 已独立覆盖这些项目，不改写旧 `not_run` 字段。

OIDC 旧账号需按[配置与迁移说明](../guides/configuration.md)核验主体后显式绑定；无凭证的历史未知写入继续阻断，结案契约见[故障手册](../operations/incident-runbook.md)。本次没有变更数据库 schema、迁移业务库或连接真实模型与支付服务。

## 上一批本地验收

以下结果于 2026-11-09 在基于 `eccd6eb` 的工作树上生成；[原检查清单](../evidence/improvement-loop/checks.json)及证据保持原样，不表示本次修复重新取得同一长期负载测量。

| 范围 | 结果 | 证据与口径 |
|---|---|---|
| 完整回归 | **428 项通过，无跳过；85.492 秒** | [日志](../evidence/improvement-loop/unittest.log)，Python 3.11，含真实 HTTP/MCP、Chromium 和新增 CLI/UI 协议 |
| app 语句覆盖率 | **82%** | [覆盖率](../evidence/improvement-loop/coverage.log)，不含脚本和独立进程 |
| 持续负载 | 180 秒、3 worker、3600 次请求；接受的 **2891/2891 完成**，709 次 429 | [摘要](../evidence/improvement-loop/postgres-load.json)，PostgreSQL 17.11、受控 HTTP 模型、四种任务，限流单独计数 |
| 负载延迟与资源 | 端到端 p95 2160 ms，排队 p95 1883 ms；排空 2.14 秒；观测积压最高 24、数据库连接最高 10 | 同一报告；应用进程合计采样 RSS 峰值约 1351 MiB，不含 PostgreSQL；本机测量不能当生产容量 |
| 故障恢复 | 队列饱和、领取后 worker 退出、PG 停启、模型 HTTP 中断通过 | 同一报告 drills；worker 接管约 1.46 秒、PG 恢复约 1.73 秒，不是生产 RTO |
| 索引规模 | 1000/10000 个合成 chunk 输出一致；万级 BM25 p50 **510.59 → 17.85 ms** | [报告](../evidence/improvement-loop/index-scale.json)，预编译热缓存；冷读 381 ms、编译 998 ms，非 ANN/语义质量评测 |
| 多轮售后 | 补充资料、改诉求、旧提案失效、重启、新申请撤回、确认执行幂等通过 | 完整回归中的 dialogue_intake / improvement_boundaries；包含字段来源、过期 owner、接管释放 ABA 与计划草稿 |
| 版本评测闭环 | 任务收集去重 → 脱敏整理 → 冻结 → 导出 → 开发集比较通过 | [CLI 证据](../evidence/improvement-loop/dataset-loop.json)，1 条合成演示题、4 组比较，批准数仍为 0 |
| 双数据库 | 升级、无 schema drift、业务/知识/数据版本 smoke、降级重建通过 | [迁移摘要](../evidence/improvement-loop/migrations.json)；非空数据集降级保护另有回归 |
| 计划与静态检查 | 40 项确定性计划门禁、计划基准、Ruff、compileall、OpenAPI 通过 | [证据目录](../evidence/improvement-loop/README.md)；OpenAPI 101 个路径 |

完整回归在不含本地旧数据库、私有 .env 的临时源码副本中运行，Python 与前端内容哈希在生成时与当时的工作树一致；原默认演示数据库保留。PostgreSQL 使用随机口令、回环端口和临时目录，验收后停止清理，无业务库迁移。

## 历史结果仍可追溯

旧实现 `7565683` 的 [Actions 42054871319](https://github.com/scallion7/xc_sx_agent/actions/runs/42054871319) 曾通过 8/8 作业，包含 Python 3.10–3.12、双数据库、供应链、浏览器与 Compose。该结果不代表当前改动的 CI 状态。

18 项任务基线、三条复杂售后 HTTP 工作流和 64 组检索配置比较保留在[历史证据](../evidence/README.md)。本次没有重写旧日志、冻结数据或原第 1–34 期说明，也未重新宣称检索质量提升。

## 后续自费验证清单（当前项目范围外）

以下工作仅作为后续扩展参考，需要自行安排人力、模型与基础设施预算，当前项目不执行，也不作为本次工程交付的完成条件。若后续启动，仍需满足各项真实验收要求。

| 工作 | 当前状态 | 必要条件 |
|---|---|---|
| 人工金标准 | 后续自费验证；原 18 份政策、32 题未完成真实审核，版本工作流已实现 | 自行安排审核人力，使用[复核工作台](../guides/review-workbench.md)；新版本通过 `requires_second_review` 标记需要双人复核的题目 |
| 原冻结保留集 | 后续自费验证；16 题 holdout 未运行 | 完成全量真实审核，遵守[离线评测协议](offline-review.md) |
| 真实 embedding / 模型效果与费用 | 后续自费验证；未验证，付费模型调用为 0 | 自备模型服务、调用预算、数据与评测方案 |
| 生产身份与供应商 | 后续自费验证；未连接真实订单、支付或组织身份 | 自备目标环境、凭据与联调资源，核验幂等/查单契约 |
| 生产 SLA 与灾备 | 后续自费验证；本机持续负载通过，跨机、高可用、PITR、跨区域恢复未验收 | 自备部署与压测资源，明确业务流量模型和恢复目标 |

证据支持检查是保守原文规则，不能称为语义蕴含验证；本地哈希向量、词法重排和合成标签不能证明真实语义效果。任务 completed 不等于业务答案正确率，发布报告的完整性门禁也不代替对回答内容的独立核对。对话草稿与索引缓存有明确事务和版本边界，整套旧业务仍不宣称共享库 SaaS 或真实支付 exactly-once。

复现入口：[多轮办理与索引](../engineering/improvement-loop.md) · [版本化评测](versioned-datasets.md) · [持续负载](../operations/sustained-load.md) · [配置与测试](../guides/configuration.md)。
