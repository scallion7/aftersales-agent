# 简历表述与贡献准备

[展示材料](README.md) · [项目卡](project-card.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

下方首版面向大模型应用与 Agent 开发岗位，可直接选入简历。项目周期和个人职责按实际情况填写；版面有限时使用短版。当前项目聚焦系统搭建、Agent 技术探索与工程验证，范围见[项目范围](../evaluation/acceptance.md#project-scope)。

## 大模型应用与 Agent 开发岗位 · 推荐版

**电商售后智能体平台｜Agent 工作流与可靠执行**

**技术栈：** Python、FastAPI、SQLAlchemy/PostgreSQL、RAG、MCP、Playwright、Docker Compose、GitHub Actions。

**项目简介：** 面向订单咨询与售后办理，搭建集政策检索、多轮申请、工具执行和人工协作于一体的 Agent 平台，探索模型推理与确定性业务执行的协作机制，并通过受控环境验证任务恢复、业务一致性和评测发布流程。

- **Agent 编排与工具接入：** 整合 ReAct、Plan-and-Execute 与多 Agent 路由，通过统一工具执行层接入业务 API 与 MCP；实现多轮申请草稿、用户确认、人工审批及客服接管，贯通查询到售后办理的业务流程。
- **RAG 与政策证据：** 实现 BM25、余弦检索与 RRF 融合，结合政策适用条件过滤、版本化知识快照、原文引用及冲突检查；绑定订单与多轮上下文，对证据不足或政策冲突场景转入澄清或人工处理。
- **可信执行与故障恢复：** 将操作提案绑定身份、会话、参数及业务版本，结合 SQL 持久化任务、租约与 fencing、幂等约束和退款查单对账，覆盖重复确认、诉求变更、Worker 中断及外部响应丢失等故障场景。
- **评测与工程验证：** 构建可分批续跑的受控评测及配置发布门禁，校验关键事实、引用、原始报告和完整性；本地 **500 项回归全部通过、无跳过，app 语句覆盖率 82%**，固定提交的 CI **9/9 作业通过**，覆盖 Python 3.10–3.12、双数据库迁移、浏览器和容器验收。

## AI 后端与平台工程方向

- 基于 FastAPI 与 SQL 存储构建持久化 Agent 任务和独立 Worker，通过租约、fencing、状态 CAS 与事件记录支持进程退出后的任务接管，控制过期 Worker 的本地状态提交。
- 实现可信操作提案、工单唯一约束和退款对账；HTTP 商务路径使用 Outbox/Inbox，普通外部适配器沿用稳定业务键查单，对超时和不完整回执保留待核对状态，避免盲目重复提交。
- 建立 SQLite/PostgreSQL 迁移、浏览器交互与故障恢复验证。2026-11-16 本地验收 500 项回归通过、无跳过，app 语句覆盖率 82%；固定提交的 GitHub CI 完成 Python 3.10–3.12、Compose 等 9 个作业。

上述 500 项和 82% 来自[2026-11-16 本地复验](../evidence/dependency-patch-20261116/checks.json)，覆盖率不包含 `app/scripts/*` 及独立进程；9/9 对应 [`deaa9a9` 的 CI](https://github.com/scallion7/xc_sx_agent/actions/runs/43853072534)，不表示本文修订后产生了新的测试结果。代码与测试映射见[项目卡](project-card.md)，CI 作业不与本地用例数相加。

## 版面有限时的短版

> 搭建电商售后 Agent 平台，整合 ReAct、Plan-and-Execute、多 Agent 路由及 MCP 工具，支持 RAG 政策证据、多轮申请与可信确认；实现任务恢复、幂等退款对账和评测发布门禁。本地 500 项回归全部通过，app 语句覆盖率 82%。

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
