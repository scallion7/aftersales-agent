# 三个可复现演示

[展示与面试](README.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md) · [录像与复录](recording.md)

面向面试和课堂，分别展示正常业务、异常恢复、评测发布。每个演示先说明业务问题，再展示操作和可检查结果。下面的流程使用合成订单、临时或专用演示数据库、受控模型，不连接真实支付或付费模型。

## 演示前准备

按[配置指南](../guides/configuration.md)安装锁定依赖，推荐 Python 3.11。命令均在仓库根目录、已激活虚拟环境的终端运行。浏览器演示可手动打开系统浏览器；自动录制另需安装项目对应的 Chromium。

演示 A 的目录必须是本场专用的新目录。下面两条命令中的 `showcase-01` 应一起更换，避免串入上一场的数据。目录检查失败时换一个新名字。

```bash
python -c "from pathlib import Path; assert not Path('app/sessions/showcase-01').exists(), '请换一个全新的演示目录'"
python -m app.scripts.demo_stack --intake --directory app/sessions/showcase-01
```

启动器打印动态 URL、客户令牌 `demo-user` 和客服令牌 `demo-admin`。只使用打印出来的本机地址。首次安装时间不计入五分钟演示。演示 B、C 自行创建和清理临时库，可在另一终端执行，不复用 A 的数据库。

## A · 正常办理，约五分钟

完整操作步骤见[五分钟演示](../guides/five-minute-demo.md)。下表是讲解时使用的提词卡。

| 时间 | 操作与画面 | 讲解重点 | 必须观察到的结果 |
|---|---|---|---|
| 0:00–1:00 | `/workspace` 连接 `demo` 会话，查询 `ORD-20240125-006` | 订单归属由服务端身份决定 | 返回对应合成订单 |
| 1:00–2:00 | 发送“请说明七天退货政策”，在证据栏检索“七天退货” | 回答可以追溯到知识版本和原文 | 展示引用、版本与片段定位 |
| 2:00–3:30 | 依次发送“售后申请”“补充订单 ORD-20240125-006”“补充原因：尺寸不合适”“生成提案”，每轮等待完成 | 草稿保存与业务执行有独立步骤 | 显示资料来源和待确认的具体操作 |
| 3:30–4:00 | 核对参数，点击一次“确认并执行” | 确认绑定操作及参数，服务端执行业务检查 | 创建工单，有可追溯编号；此时不宣称退款完成 |
| 4:00–5:00 | `/workbench` 刷新待办，接管 `user-1 / demo`，发送人工消息；客户页重新连接 | 所有权变更约束后续自动调用 | 客户页显示人工服务状态与消息 |

可选追问演示：在点击确认前发送“改为换货”，展示旧提案失效，再生成新提案。不能把已执行的外部退款解释为可以通过修改草稿直接撤销。

讲解收束语可用：“这条主线把自然语言申请转成可核对的业务状态。下一段查看网络中断时怎样避免重复退款。”正常运行结束按 `Ctrl+C`，启动器停止自己的子进程，专用目录保留供复盘。

## B · 退款已提交，响应丢失，约三分钟

问题：供应商可能已经接受退款，客户端却没有拿到结果。直接创建新操作重试会产生重复执行风险。

```bash
COMPLEX_TASK_REPORT_DIR=test-results/showcase-01/refund \
  python -m unittest tests.test_complex_after_sale_http.ComplexAfterSaleHttpTests.test_unknown_refund_restart_and_reconciliation -v
```

PowerShell 先执行 `$env:COMPLEX_TASK_REPORT_DIR='test-results/showcase-01/refund'`，再执行上方 `python -m unittest ... -v` 部分。完成后可执行 `Remove-Item Env:COMPLEX_TASK_REPORT_DIR` 清理此环境变量。再次展示时使用新的报告目录。

测试启动真实回环 HTTP API 和独立业务沙箱，在合成退款提交后断连并丢弃回调，随后重启沙箱并查单。整体预期是 `Ran 1 test` 和 `OK`。生成的 `test-results/showcase-01/refund/unknown-refund-recovery.json` 可直接打开，也可摘要查看。

```bash
python -c "import json; from pathlib import Path; r=json.loads(Path('test-results/showcase-01/refund/unknown-refund-recovery.json').read_text()); print(json.dumps({'scenario': r['scenario'], 'passed': r['passed'], 'final_counts': r['final_counts']}, ensure_ascii=False, indent=2))"
```

| 镜头 / 阅读点 | 对应事实 | 应如何解释 |
|---|---|---|
| [故障注入与重放断言](../../tests/test_complex_after_sale_http.py)中的 `test_unknown_refund_restart_and_reconciliation` | 接收后断连，返回结果未知 | 未收到响应不能直接判定业务失败 |
| 原操作 ID 与对账记录 | 重放复用原操作，恢复后查询供应商 | 稳定业务键连接请求、查单与凭证 |
| 报告 `final_counts` | `cases=1`、`operations=1`、`provider_refunds=1` | 这次沙箱故障演练没有产生第二笔退款 |

这里验证的是本次故障路径的执行契约。供应商是真实 HTTP 沙箱，退款数据为合成数据；此结果不构成真实支付服务的生产保证。[退款执行边界](../engineering/reliable-execution.md)

## C · 评测不完整，拒绝发布，约三分钟

问题：报告文件存在或部分题目通过，并不足以允许配置上线。

```bash
python -m unittest tests.test_agent_quality_cli.QualityTests.test_two_batches_publish_the_pinned_release_without_touching_knowledge_head -v
```

使用[这条端到端测试](../../tests/test_agent_quality_cli.py)作为讲解代码，定位同名方法，依次查看 `cli(...)` 调用和紧随其后的断言。该测试使用两条临时开发题、独立 SQLite 和本机受控模型。不要用它的自动化测试数据替代人工复核。

| 顺序 | 操作 | 可检查结果 |
|---|---|---|
| 1 | 创建绑定目标知识快照的配置草稿 | 草稿有固定的配置与评测输入 |
| 2 | 只完成 1/2 格，然后尝试导入发布报告 | 发布 CLI 非零退出，目标配置仍是草稿 |
| 3 | 使用 `--resume` 补足到 2/2 格 | 已有格复用，报告达到完整矩阵 |
| 4 | 导入完整报告并激活测试配置 | 发布头指向受评草稿；源知识活动头保持不变 |
| 5 | 篡改摘要中的原件 SHA-256 后读取 | 原件校验拒绝该报告 |

整个命令预期输出 `Ran 1 test`、`OK`。拒绝发布属于测试内部已断言的预期结果，所以终端不一定打印发布子进程的错误详情。现场应同时展示源码中的“非零退出”和“草稿未变化”断言，不能把 `OK` 解释成不完整报告也成功发布。

原 32 题人工审核、原 16 题保留集和真实模型评测继续等待人工审核完成。这条演示只使用独立的开发测试材料，不执行这些待办。[评测发布协议](../evaluation/offline-review.md)

## 时间不足和故障处理

- 五分钟场合只演示 A，给出 B、C 的命令与已记录证据。十至十五分钟场合依次展示三项。
- 网络受限时，提前安装锁定依赖和 Chromium。演示运行本身只使用回环服务。
- A 启动失败先看专用目录的 `api.log`、`worker.log`、`model.log`；不要改用个人 `.env` 或真实模型端点救场。
- B、C 失败时保留输出，使用[录制材料](recording.md)并注明是已验证版本的录像；不要把旧录像说成现场运行成功。
- 进入教学时，转到[分层实验](../learning/README.md)，让学员解释每个断言阻止了哪种错误。
