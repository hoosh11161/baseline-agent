# Round 4 Windows 换机运行与提交指南

本文面向拿到仓库后第一次在另一台 Windows 电脑运行比赛 Agent 的同学。代码仓库和官方比赛系统是两部分：仓库提供 Agent，官方比赛系统提供 TongSIM、赛题服务和最终结果打包工具。两部分都需要准备。

## 1. 准备文件

1. 从官方比赛资料下载与电脑架构匹配的 Windows 比赛系统，并保留资料中的《初赛系统使用指南》。
2. 克隆参赛仓库：

   ```powershell
   git clone https://github.com/jackzhu119/baseline-agent.git
   cd baseline-agent
   git checkout main
   ```

3. 若 `main` 尚未包含 Round 4，可临时切换：

   ```powershell
   git fetch origin
   git checkout codex-optimization-round-4
   ```

不要把官方系统中的结果文件、模型密钥或 `.env` 提交到 Git。

## 2. 安装固定 Python 环境

本轮已验证环境为 Python 3.12.14。Python 3.14 会使锁定的 `tiktoken==0.8.0` 尝试本地 Rust 编译，不建议用于比赛。

先安装 [uv](https://docs.astral.sh/uv/)，然后在仓库根目录执行：

```powershell
uv python install 3.12.14
uv sync --python 3.12.14 --extra dev
uv run --python 3.12.14 python scripts/generate_pb2.py
Copy-Item config.toml.example config.toml
```

验证基础环境：

```powershell
uv run --python 3.12.14 python -m pytest -q
uv run --python 3.12.14 python -m compileall -q arenaagent scripts tests
uv run --python 3.12.14 python scripts/replay_episode.py examples/public_trace_example.json
```

交付版本的预期结果是：109 tests passed、compileall 无输出且退出码为 0、replay 状态为 `PASS`。replay 只验证公开轨迹与本地保护逻辑，不代表官方得分。

## 3. 配置 Agent

打开 `config.toml`，通常只需确认：

```toml
[preliminary_baseline_agent]
name = "preliminary_baseline_agent"
tongsim_server_endpoint = "127.0.0.1:50060"

[grpc]
endpoint = "127.0.0.1:50051"
```

端口只有在官方赛题系统和 TongSIM Proxy 已启动后才会连通。不要随意修改 protobuf、gRPC 定义或官方端口。

模型密钥只放环境变量。以下示例仅展示变量名，不要把真实值写入文件或聊天记录：

```powershell
$env:OPENAI_API_KEY="在此会话中临时设置"
```

项目也支持 `AZURE_OPENAI_API_KEY`、`DASHSCOPE_API_KEY`、`ZHIPU_API_KEY`、`ARK_API_KEY`。只设置实际使用的渠道。

## 4. 启动顺序

1. 按官方《初赛系统使用指南》启动仿真客户端。
2. 按官方指南启动赛题系统与 TongSIM Proxy。
3. 在仓库根目录检查环境：

   ```powershell
   uv run --python 3.12.14 python scripts/preflight.py --release-dir "D:\比赛系统\release"
   ```

4. 只有当输出中 Python、导入、模型资产、模型凭据、50051、50060 和 official release 均为 `PASS` 时，才开始真实评测。
5. 初赛 Agent 示例：

   ```powershell
   uv run --python 3.12.14 arenaagent --agent_name preliminary_baseline_agent --config config.toml --vlm_model VLMGPT5Config --run_times 5
   ```

模型类名必须是本机已配置且能调用的模型。可先列出项目支持项：

```powershell
uv run --python 3.12.14 arenaagent --agent_name vlm_agent --get_vlm_model
```

## 5. 真实评测与定位失败

真实运行后，先保留 `logs/metrics/episode_*.json` 和 `failure_*.json`，再执行：

```powershell
uv run --python 3.12.14 python scripts/benchmark.py --metrics-dir logs/metrics --output-dir benchmark/local_official
uv run --python 3.12.14 python scripts/failure_analyzer.py --metrics-dir logs/metrics --output-dir benchmark/local_failures
uv run --python 3.12.14 python scripts/model_benchmark.py --metrics-dir logs/metrics --output-dir benchmark/local_models
```

只有官方任务服务判分且 `verified=true` 的 episode 才能用于声称成功率、得分或模型优劣。出现失败时优先查看第一关键失败，而不是只看最后一步。

## 6. 结果打包

官方 release 的具体目录和命令以随比赛系统附带的指南为准。当前 Windows 工具常见流程是在 release 目录执行：

```powershell
.\start_test.bat package-results
```

打包前确认 `arena_offline` 下已经产生全部五类任务结果：Counting、Jigsaw、NPC、Raven、TidyRoom。成功后工具会给出 `result_package.bin` 的实际路径。只提交官方工具生成的包，不要手工改 `.bin`。

## 7. 常见问题

- `tiktoken` 要求 Rust 编译：确认命令使用 `--python 3.12.14`，不要用系统 Python 3.14。
- 找不到 `*_pb2.py`：重新执行 `scripts/generate_pb2.py`。
- 50051/50060 超时：官方服务没有启动、启动顺序不对，或防火墙拦截；先修服务，不要让 Agent 在离线状态反复尝试。
- 测试通过但比赛没分：单元测试和 replay 不等于真实 TongSIM；检查官方 episode 是否有 `verified=true` 和 score。
- 模型超时/限流：Agent 会进行一次短上下文重试，再使用保守策略；仍需检查模型账号配额和网络。
- 要把代码发给下一位同学：优先发 Git 仓库地址与 commit SHA，不要复制带 `logs`、缓存、结果包和密钥的整个工作目录。

## 8. 接收方验收清单

- `git rev-parse HEAD` 与交付 SHA 一致。
- Python 为 3.12.14。
- 109 项测试通过。
- compileall 通过。
- offline replay 为 `PASS`。
- preflight 中 50051、50060 和模型凭据均为 `PASS`。
- 真实 episode 指标由官方服务验证。
- 五类结果文件齐全，`result_package.bin` 由官方脚本生成。

