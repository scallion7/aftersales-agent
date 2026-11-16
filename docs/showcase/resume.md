# 简历表述与贡献准备

[展示材料](README.md) · [项目卡](project-card.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

项目维护者为 [scallion7](https://github.com/scallion7)。下方提供两套可选表述，每套保留三条，按投递岗位选择一套。项目周期、承担范围和熟悉程度按实际情况填写，工程完成记录与个人面试能力分别准备。

## 项目名称与简介

**Ecom Service Agent｜电商售后智能体平台**

围绕订单咨询与售后办理，扩展政策检索、多轮申请、可信操作确认、人工审批与客服接管流程，并实现可恢复任务、退款对账和版本化评测发布。支持本地隔离演示、浏览器回归与双数据库验证。

技术栈可按版面选取 Python、FastAPI、SQLAlchemy、PostgreSQL、RAG、MCP、Playwright 和 GitHub Actions；面试准备时再展开其具体职责。

## Agent 与大模型应用方向

- 围绕电商售后流程整合 ReAct、Plan-and-Execute 与多 Agent 路由，结合版本化政策检索和多轮申请草稿，实现查询、证据引用、补充资料、用户确认与人工协作的业务闭环。
- 将模型工具建议接入统一执行层，以身份与会话校验、参数及业务版本绑定、人工审批和持久化幂等约束高风险操作，覆盖拒绝、诉求修改、重复确认及客服接管后的授权失效。
- 建立固定知识快照、分批续跑、原始回答校验与配置发布流程；受控开发矩阵覆盖 9 个业务家族和 3 种策略，校验关键事实、原文引用及转人工原因，并阻止缺项、篡改或评分失败的报告进入发布。

## AI 后端与平台工程方向

- 基于 FastAPI 与 SQL 存储构建持久化 Agent 任务和独立 Worker，通过租约、fencing、状态 CAS 与事件记录支持进程退出后的任务接管，控制过期 Worker 的本地状态提交。
- 实现可信操作提案、工单唯一约束和退款对账；HTTP 商务路径使用 Outbox/Inbox，普通外部适配器沿用稳定业务键查单，对超时和不完整回执保留待核对状态，避免盲目重复提交。
- 建立 SQLite/PostgreSQL 迁移、浏览器交互与故障恢复验证。2026-11-13 本地验收 500 项回归通过、无跳过，app 语句覆盖率 82%；对应实现提交的 GitHub CI 完成 Python 3.10–3.12、Compose 等 9 个作业。

两套要点的代码、测试和结果来源集中在[项目卡](project-card.md)。其中 500 项和 82% 是 2026-11-13 的本地记录，CI 作业不与本地用例数相加。

## 版面有限时的短版

> 围绕电商售后构建 Agent 业务闭环，支持政策证据、多轮申请、可信确认和人工接管；实现持久化任务、幂等退款对账及版本化评测发布。2026-11-13 本地 500 项回归通过，app 语句覆盖率 82%。

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

32 题人工审核、16 题原冻结保留集和真实模型效果评测尚未完成。简历暂不填写“模型准确率 100%”“业务成功率提升”“节省客服成本”等效果指标；受控 27 格通过只能对应已实现的评分与发布流程。性能数字如需引用，必须同时保留具体环境、负载和测量日期，当前短版因此使用更容易核验的回归与覆盖率记录。

面试追问的回答思路与讲解顺序见[讲解与追问](interview.md)。
