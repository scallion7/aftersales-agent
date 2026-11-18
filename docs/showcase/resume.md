# 简历表述与贡献准备

[展示材料](README.md) · [项目卡](project-card.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

推荐版面向大模型应用与 Agent 开发岗位。一页简历可直接选用下面三条，项目周期和个人职责按实际情况填写。面向后端岗位或版面有限时，可选用后文对应的版本。[项目范围](../evaluation/acceptance.md#project-scope)

## 大模型应用与 Agent 开发岗位 · 推荐版

**电商售后智能体平台｜政策问答与可靠执行**

**技术栈**　Python、FastAPI、SQLAlchemy、PostgreSQL、RAG、MCP、Playwright、Docker Compose、GitHub Actions。

**项目简介**　AfterSales Agent 面向订单咨询与售后办理，搭建集政策检索、多轮申请、工具执行和人工协作于一体的 Agent 平台，探索模型推理与确定性业务执行的协作机制，并通过受控环境验证任务恢复、业务一致性和评测发布流程。

## 一页简历 · 三条精简版

- **售后 Agent 工作流**　基于 FastAPI 构建订单咨询与多轮售后流程，接入业务工具和 MCP。将用户确认绑定到具体订单、操作参数和业务版本，支持修改诉求、撤回申请及客服接管。
- **有依据的政策问答**　结合 BM25、向量检索与 RRF 排名融合，按商品、付款状态和当前订单核对政策原文。在合成政策、本地哈希检索和受控模型网关下，40 道单轮题和 6 段对话的 17 轮中，符合预期的结果由 **32/57 提高到 57/57**。[逐题结果](../evaluation/policy-transfer.md)
- **退款可靠执行**　通过 SQL 持久化任务、Worker 租约、幂等键和退款对账处理重复确认、进程中断与回执丢失。在 PostgreSQL 并发回归中，8 个 Worker 争抢同一任务，仅 1 个领取成功。同一退款的 10 次回调仅 1 次生效。[并发验证记录](../evidence/agent-boundaries-20261118/postgres.json)

**工程验证**　启用 Chromium 的本地回归 **554 项全部通过，零跳过，app 语句覆盖率 84%**。此前政策问答修复提交 `e0271e8` 的 GitHub CI **9/9 作业通过**。[本地验收](../evidence/aftersales-rename-20261118/checks.json) · [CI 运行](https://github.com/scallion7/aftersales-agent/actions/runs/44317537941)

### 展开技术细节时可选

- **工作流与工具**　整合 ReAct、Plan-and-Execute 与多 Agent 路由，通过统一执行层接入业务 API 与 MCP。申请草稿保留每轮补充的信息，具体操作经用户确认后执行，高风险工单进入人工审批。
- **政策证据**　结合版本化知识快照、政策条件过滤、原文引用及冲突检查。用户切换订单时重新核对适用条件，证据不足时追问或转人工。
- **故障恢复与评测**　通过租约与 fencing 限制旧 Worker 提交状态，利用稳定业务键查询退款终态。受控评测支持分批续跑，配置发布前校验关键事实、引用和原始报告的完整性。

## AI 后端与平台工程方向

- 基于 FastAPI 与 SQL 存储构建持久化 Agent 任务和独立 Worker，通过租约、fencing、状态 CAS 与事件记录支持进程退出后的任务接管，控制过期 Worker 的本地状态提交。
- 实现可信操作提案、工单唯一约束和退款对账；HTTP 商务路径使用 Outbox/Inbox，普通外部适配器沿用稳定业务键查单，对超时和不完整回执保留待核对状态，避免盲目重复提交。
- 建立 SQLite/PostgreSQL 迁移、浏览器交互与故障恢复验证。本地启用 Chromium 后，554 项回归全部通过，零跳过，app 语句覆盖率 84%。GitHub CI 的 9 个作业全部通过，覆盖 Python 3.10–3.12、双数据库迁移及 Compose 验收。

2026-11-18 的本地验收使用 Python 3.11.15。覆盖率统计主测试进程中 `app` 的语句，排除 `app/scripts/*`。政策问答的 57 项按预期处理和引用逐项判定，部分失败题参与了修复。全部使用合成数据，标签未经独立人工审核。[本地验证记录](../evidence/aftersales-rename-20261118/checks.json) · [政策问答原始结果](../evidence/policy-transfer-20261118/cases.json) · [项目卡](project-card.md)

## 版面有限时的短版

> 搭建电商售后 Agent 平台，接入业务工具与 MCP，支持多轮申请、用户确认和退款对账。按商品、付款状态和订单核对政策原文，合成政策与受控模型下的 40 道单轮题及 17 个对话轮次由 32/57 提高到 57/57。本地 554 项回归全部通过，零跳过，app 语句覆盖率 84%。

## 每条简历要点准备四项依据

| 要点 | 能举出的失败例子 | 能打开的实现与测试 | 能解释的取舍 |
|---|---|---|---|
| 可信确认 | 模型自报确认、用户修改参数后继续使用旧 action | [actions.py](../../app/services/actions.py)、[trusted actions](../../tests/test_trusted_actions.py) | 授权过期与重新确认增加操作步骤，但保留用户对具体操作的控制 |
| 任务恢复 | Worker 领取后退出，旧 Worker 随后恢复 | [runs.py](../../app/repositories/runs.py)、[async runs](../../tests/test_async_runs.py) | SQL 队列便于事务一致性，容量与调度能力需按真实部署另测 |
| 退款对账 | 供应商已受理，响应丢失 | [refund workflow](../../app/services/refund_workflow.py)、[external refund recovery](../../tests/test_external_refund_recovery.py) | 未知结果阻塞等待证据，恢复速度受供应商查单能力约束 |
| 政策检索 | 前 K 条未显示矛盾条款，或用户换单仍沿用旧条件 | [retrieval.py](../../app/platform/retrieval.py)、[policy context](../../tests/test_policy_context.py) | 依赖结构化政策元数据和保守来源规则，不能包办任意语义矛盾判断 |
| 评测发布 | 回复无关但任务完成，或摘要被手动改成通过 | [agent quality](../../app/platform/agent_quality.py)、[quality CLI](../../tests/test_agent_quality_cli.py) | 原文事实规则可重复审计，对自由改写较严格 |

## 结果与归属的填写边界

项目的演进、代码和提交依据见[贡献说明](../CONTRIBUTIONS.md)。可以说明围绕原型做了哪些扩展，避免将框架、通用协议或已有技术写成个人发明。面试时选自己能解释和复现的部分展开，尚未掌握的模块先沿[分层教学](../learning/README.md)补齐。

人工审核、真实模型效果评测和生产环境验证统一列为**后续自费验证，当前项目范围外**，需另行安排审核人力、模型调用及部署资源。原 32 题真实审核尚未完成，16 题冻结保留集和真实模型评测未运行，不计入本项目已验证成果；本项目当前负责系统搭建、技术探索与受控工程验证。

简历使用已实现机制和可核验的工程结果，不填写“模型准确率 100%”“业务成功率提升”“节省客服成本”等未经验证的效果指标。受控 27 格通过只对应评分与发布流程，默认余弦检索使用本地哈希向量，不能据此声称真实语义效果提升。性能数字如需引用，须同时保留环境、负载和测量日期。

面试追问的回答思路与讲解顺序见[讲解与追问](interview.md)。
