# 教学环境与实验记录

[课程路线](README.md) · [文档中心](../README.md) · [当前验收](../evaluation/acceptance.md)

使用独立的学习检出和 Python 3.11 虚拟环境。从准备存放项目的父目录开始克隆，进入 `aftersales-agent` 后，在仓库根目录运行后续 Bash/Zsh 命令。Windows 环境创建与激活方式见[配置指南](../guides/configuration.md)。首次安装依赖需要网络，完成安装后的九个主实验不需要真实模型服务。人工金标准审核、真实模型效果与生产环境验证统一列为[后续自费验证](../evaluation/acceptance.md#project-scope)，当前学习环境无需准备这些资源。

## 准备环境

```bash
git clone https://github.com/scallion7/aftersales-agent.git
cd aftersales-agent
git switch -c codex/learning-labs
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-lock.txt
python -m pip check
git rev-parse HEAD
python --version
```

保留 `git rev-parse HEAD` 的结果，后续报告引用这个实际提交。课程基于当前实现编写，既有 2026-11-13 验收数字仍属于原记录；在学习分支上运行的结果单独记载。

这个检出无需创建 `.env`，也不要复制业务环境的 `.env`、数据库或账号密钥。打开没有注入 `DATABASE_URL`、OIDC、模型或 Provider 配置的终端，避免测试的环境配置与业务配置混用。不要为了批量运行给所有测试统一指定一个数据库，即使它是临时库，也可能覆盖某些迁移或子进程 fixture 的目标。业务状态、恢复和评测测试的 fixture 大多创建临时数据库并自动清理；第一层的部分应用工厂和工具注册表测试仍可能创建或使用学习检出内默认的 `app/sessions/xc_sx_agent.db` 与日志。必须在上面新建的独立学习检出中执行，不能把全部测试描述为自动清理或在业务检出上照搬。

## 首次检查与可视演示

```bash
python -m unittest tests.test_architecture.ApplicationFactoryTests -v
test ! -e app/sessions/learning-smoke-01 && \
  python -m app.scripts.demo_stack --intake --smoke --directory app/sessions/learning-smoke-01
```

第一条检查三个应用工厂用例，模型客户端是测试替身。第二条启动回环地址上的 API、Worker、受控 HTTP 模型和库存 MCP，执行烟测后退出。执行前确认 `app/sessions/learning-smoke-01` 尚不存在，重跑时换新目录名称；烟测数据和日志会保留在该目录。它允许本机进程通信，不要求接入互联网模型；环境需要允许绑定 `127.0.0.1` 端口。

要保持界面运行，使用下面的命令，按[五分钟演示](../guides/five-minute-demo.md)操作。`app/sessions/learning-demo-01` 应为本次新目录，下次演示换新名称。

```bash
python -m app.scripts.demo_stack --intake --directory app/sessions/learning-demo-01
```

启动器打印动态端口，直接使用打印的地址。结束时按 `Ctrl+C` 停止本次启动的进程；指定目录中的合成数据和日志保留，便于复盘。启动器的业务 Provider 为本地 mock，不会产生真实退款。

## 主实验和扩展检查

每个实验的基线命令使用 `python -m unittest` 和明确的测试类或方法。以下历史脚本包含真实模型或 embedding 调用路径，**不作为课堂执行命令**：`tests/test_agent.py`、`tests/test_react_agent.py`、`tests/test_rag.py`、`tests/test_mcp.py`。阅读历史代码时，回到课程列出的受控测试验证机制。

九个实验的基线不需要 Chromium。想验证浏览器交互时，再安装项目对应的浏览器并运行完整检查。

```bash
python -m playwright install chromium
python -m app.scripts.quality_platform --browser
```

`quality_platform` 会运行格式、静态、编译、回归、覆盖率、OpenAPI、文档链接与计划质量检查。浏览器未安装或未启用时的跳过不能记录为浏览器通过。完整回归会启动临时子进程和本机 HTTP 服务；有限实验通过与整套回归通过要分别记录。

不要在主实验中运行 `quality_platform --database`。它会使用当前环境指定的数据库进行迁移和写入，双数据库选做任务按[隔离配置说明](../guides/configuration.md)另设可丢弃目标。

## 实验记录模板

将以下内容保存在自己的学习笔记中。仓库的既有成功记录不自动填入学员报告。

```text
实验编号与主题：
实际日期与 Git 提交：
Python 版本与环境：
使用的模型/业务替身、数据库与网络范围：
运行前预测：
基线命令及实际结果：
新增测试文件、类、方法：
新增用例命令及实际结果：
正例的关键状态或业务记录数：
负例的错误/状态及副作用记录数：
机制解释与代码入口：
本实验没有证明的结论：
```

## 常见环境问题

| 现象 | 处理方法 |
|---|---|
| 模块找不到 | 确认当前目录是仓库根目录，虚拟环境已激活 |
| `test_learning_*` 找不到 | 这是作业方法；先将自己的实现或参考答案加入指定类，再执行作业验收命令 |
| `Ran 0 tests` | 检查是否误用了只定义普通函数的历史脚本，改用课程给出的 unittest 路径 |
| 本机 HTTP 无法启动 | 检查回环监听权限；先运行不启动 HTTP 的实验，保留失败日志，不记为通过 |
| 页面端口不符 | 使用本次启动器输出，不复用上一场地址 |
| 浏览器缺少可执行文件 | 在当前虚拟环境安装对应 Chromium，不用跳过结果替代验收 |
| 运行到真实服务 | 停止该次运行，检查终端与 `.env` 配置，重新使用独立检出和课程的受控入口 |
