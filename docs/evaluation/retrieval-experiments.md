# 检索诊断与配置对比

[文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

2026-11-18 在 `review-v1` 的 16 道开发题上重跑了四种检索模式。调整本地哈希检索的词法证据检查后，每种模式的结果状态均从判对 8 题提高到 13 题。题目使用未经人工复核的初始标签。[逐题对比证据](../evidence/agent-boundaries-20261118/retrieval-comparison.json)

当前交付聚焦检索机制、诊断工具及可复现实验流程。人工金标准与真实模型效果属于[后续自费验证](acceptance.md#project-scope)，当前项目暂不涉及；下面的历史诊断数据保留原口径。

## 2026-11-18 证据筛选复测

固定语料、问题、日期、适用范围和检索配置，在 `26d869a` 与修复后的代码上分别运行下文的配对命令。每次运行包含 8 个业务家族、16 道开发题，每题在 4 种模式下各比较两份配置，共 64 组。下表比较两个代码版本在相同配置下的表现。每次运行内部，`legacy-v1` 和 `candidate-v2` 的 64 组返回文档排序与结果状态均一致。[输入与源码哈希、分模式指标及逐题结果](../evidence/agent-boundaries-20261118/retrieval-comparison.json) · [修复前的逐候选轨迹](../evidence/agent-boundaries-20261118/retrieval-before.raw.json.gz) · [修复后的逐候选轨迹](../evidence/agent-boundaries-20261118/retrieval-after.raw.json.gz)

| 每种模式独立统计 | 修复前 | 修复后 |
|---|---:|---:|
| 候选文档召回率，BM25、Hybrid、Hybrid 加词法重排 | 100% | 100% |
| 候选文档召回率，本地哈希向量 | 92.9% | 92.9% |
| 最终证据召回率，四种模式各自的结果 | 42.9% | 78.6% |
| 判对结果状态的题数 | 8/16 | 13/16 |
| 应回答却拒答的题数 | 6 | 3 |
| 应拒答、澄清或转人工却判为可回答的题数 | 1 | 0 |

召回率是在有预期证据的 14 道题上，先逐题计算命中的预期文档比例，再取平均。状态判断覆盖全部 16 题。修复前，查询“冰箱到家以后什么时候预约安装？”时，“安装”和“预约”均命中正确文档，但问句中的虚词抬高了通过门槛。修复后的检查剔除疑问词和部分虚词，并将同一复合词的重叠子词合并计数。查询“滤芯的保修期限到底是多少？”时，单靠“保修期限”的若干子词已经无法让另一份维修政策通过，检索返回两份涉及滤芯的冲突条款。诊断中的 `evidence_terms` 和 `evidence_matches` 可用于检查计数。[检索实现](../../app/platform/retrieval.py) · [作用域、无证据与复合词回归](../../tests/test_retrieval_diagnostics.py)

每种模式共有 5 题从判错变为判对，没有原先判对的题转为判错。剩余 3 题均为按初始标签应答、实际仍返回 `no_evidence`。其中两题将“衣服”“外套”“退货”与条款中的“服饰”“退换”联系起来，另一题涉及未付预售尾款时是否自动扣款。分数仅描述这个开发集上的检索结果。此次核验使用本地哈希向量，外部模型调用为零，未运行保留集，未作发布验收。[逐题对比证据](../evidence/agent-boundaries-20261118/retrieval-comparison.json)

## 查看单次检索诊断

```bash
python -m app.scripts.review_evaluation --diagnostics \
  --output test-results/retrieval-development.json
```

页面选择 development 题目后也可运行本题诊断。诊断调用与公开检索相同的 `_search`，绕过缓存，额外保存：查询分词、日期和条件、删除/时效/适用范围原因、BM25 与向量分数和名次、RRF/重排前后分数、最终名次、词法重叠门槛、被拒候选及结果状态。公开检索响应不增加内部诊断字段。

“缺少 region/channel/product”表示需要澄清，未必被过滤；`lexical_support_rejected` 表示候选已有正分，但没有通过本地哈希投影的词法支持门槛。BM25 模式没有计算向量分数，因此诊断中的该列为 0，不能当作独立向量实验结果。

## 政策冲突与对话澄清

`top_k` 和候选池只控制展示与召回，不决定政策是否冲突。检索命中一个 `policy_key` 后，会检查同一快照内该键的全部有效决策；排在 K 之外、没有词法匹配的同键相反决策也会阻止自动回答。检查排除已删除、过期、尚未生效或明确不适用的政策，不混入其他政策键。相关政策的地域、渠道或商品条件仍未知时返回 `needs_clarification`，补齐后才判断冲突或可回答。

Agent 的 `search_knowledge` 工具支持 `region`、`channel`、`product` 和 `order_id`。首次缺少条件时追问，下一轮将用户明确补充的原文值放入相应字段；不能只把条件拼进 query。服务端只接受当前用户消息中出现的值或该会话已经核实的值，记录消息哈希，并沿用现有会话保存/恢复流程。此检查验证文字来源，不等同于现实事实核验，也不从模型摘要猜测地域或商品类别。

用户选择具体订单时，服务端通过 `CommerceService.get_order(order_id, user_id)` 检查归属，优先采用订单 `policy_context` 中的 `region/channel/product`（兼容订单同名顶层字段）。供应商没有明确字段时仍需用户澄清，不从收货地址推断购买地域，也不从商品名推断类别。模型参数与订单事实冲突会返回 `KNOWLEDGE_CONTEXT_CONFLICT`；切换订单清除旧订单的澄清条件。作用域按会话及用户保存，不跨用户复用。兼容旧知识后端的行为不变，这条流程用于版本化知识检索。

用户明确否定旧条件时，即使模型漏传更新字段也不会沿用被否定值。用户提及另一订单却未传入选择参数时，清除旧订单上下文并要求澄清；订单条件冲突后，同轮删去冲突参数重试也不会恢复旧条件。阻断绑定持久任务 ID 或单次 chat 的标识，新一轮用户可以重复相同文字完成澄清。

回归：[政策条件与多轮对话](../../tests/test_policy_context.py)，覆盖两轮补齐、实例重建、订单事实优先、跨用户/订单隔离，以及冲突判断不受 K 限制。工具结果在执行边界按结构化值脱敏；构建模型消息和恢复会话时保留 JSON 数字类型及合法 action 控制引用，敏感自由文本仍脱敏。

## 配置配对实验

```bash
python -m app.scripts.compare_retrieval \
  --baseline app/evaluation/retrieval_profiles/legacy-v1.json \
  --candidate app/evaluation/retrieval_profiles/candidate-v2.json \
  --output test-results/retrieval-comparison.json
```

`RetrievalProfile` 是不可变、有校验的实验配置，包含 tokenizer 版本、Unicode NFKC 规范化、候选池大小、RRF 参数/权重、词法重排权重和证据支持门槛。完整配置参与 SHA256 与缓存键；同名配置改参数也不会共享旧缓存。支持的 tokenizer 当前仍只有既有版本，不能填写任意名称伪装切换分词器。

默认仍使用 legacy-v1 的配置参数；输出状态遵循当前代码的作用域与政策冲突检查，不能因 profile 名称相同而假定新旧代码输出完全一致。候选 v2 仅增加 NFKC 规范化和 20 条候选池：先召回候选，再按原证据门槛过滤，最后截取 top K，从而允许候选池内的合格证据递补。没有自动降低门槛或上线候选配置。测试以受控排序复现“第一候选被拒、后续合格证据应递补”的机制。

对比使用同一知识快照、同一批 development 题目与四种模式，独立统计候选召回、最终证据召回、结果状态、错误放行、无依据引用及不必要拒答。缺失证据归因分为：索引缺失、适用性过滤、无正分、候选池之外、证据筛选拒绝、最终 top K 之外。逐题报告标识变化、改善与退化，并保存两侧完整诊断轨迹、配置哈希、原始文件哈希与代码树哈希。

以下是 [retrieval-handoff-round2 历史摘要](../evidence/retrieval-handoff-round2/comparison.json)中的 16 题 × 4 模式 = **64 组配对比较**，使用当时尚未人工审核的初始标签，不是当前提交重新取得的质量分数：

| 观测 | 基线与候选结果 |
|---|---|
| BM25 / hybrid 候选召回 | 均为 100%，只在有预期证据的题上计算 |
| 本地哈希向量候选召回 | 均为 92.9% |
| 最终证据召回 / 状态准确率 | 四模式均为 42.9% / 50.0% |
| 输出变化、改善、退化 | 64 组均无变化 |
| BM25 / hybrid 缺失证据归因 | 9 次文档实例被证据门槛拒绝；不是 9 个独立业务家族 |

该历史批次的主要损失位于证据判断阶段，扩大候选池没有改善其最终表现。**这些结果不支持语义质量提升结论。** 若后续自费验证真实效果，须先审核原始标签，再决定如何调整证据策略。[摘要](../evidence/retrieval-handoff-round2/comparison.json)关联完整压缩轨迹。实验入口只接受 development，报告始终 `release_eligible=false`；`--review` 可应用全量审核通过的标签，但不会解锁本脚本对 holdout 的运行。

## 结果与复现边界

CI 会执行上述开发集脚本，结果位于各次运行的 `platform-acceptance` 产物。已核验基线 `37e2fd7` 对应 [Actions 43442455601](https://github.com/scallion7/xc_sx_agent/actions/runs/43442455601)，后续提交从[工作流](https://github.com/scallion7/xc_sx_agent/actions/workflows/offline-quality.yml)按 SHA 查找；不要将当前运行状态与历史表格的数值合并。摘要的 `raw_artifact` 连接压缩完整轨迹与 SHA256，比较时同时核对源码树哈希、输入文件哈希、profile 哈希及标签状态。

自定义数据版本通过 `--dataset dataset-export.json` 指定；可另加 `--review review-approved.json` 应用与之匹配的完整真实审核。数据集导出和审核导出是两个文件。脚本没有 `--split holdout`、真实模型或自动发布开关，只接受 development；如果版本没有开发题，比较会被拒绝。版本准备见[数据集流程](versioned-datasets.md)。

预编译索引的速度测量见[持续负载与索引验收](../operations/sustained-load.md)。索引结果一致、缓存命中或有效引用都不等于答案语义正确；当前原文支持检查也只是一套保守规则。

实现：[配置定义](../../app/platform/retrieval_profile.py)、[比较器](../../app/platform/retrieval_experiment.py)、[CLI](../../app/scripts/compare_retrieval.py)。
