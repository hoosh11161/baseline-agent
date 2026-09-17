# TongSIM Agent 后续优化交接与 Round 6 指令词

## 仓库与基线

- Round 5 源仓库：`https://github.com/jackzhu119/baseline-agent`
- 当前身份可写交付仓库：`https://github.com/hoosh11161/baseline-agent`
- Round 5 分支：`codex-optimization-round-5`
- Round 5 起点与生产实现：`a20a67ff5b7f9f09a9a4bb552bc81cd033b83dee`
- Round 5 最终证据/文档 SHA：开始工作时以可写仓库最新 `main` 为准

Round 5 从 `jackzhu119/main@a20a67f` 开始。当前 GitHub 身份 `hoosh11161` 向 `jackzhu119` 推送时返回 403，因此成果备份和最终合并目标是可写的 `hoosh11161/baseline-agent`。下一位接手者必须先检查自己的权限与远端，不得假定两个仓库都可写，也不得 force push。

## Round 5 结论

Round 5 完整复现了当前版本：

- Python 3.12.14
- 109 tests passed
- `compileall` PASS
- public trace replay PASS，0 mismatches
- protobuf imports 与 Raven assets PASS

但真实评测前提全部不满足：

- `127.0.0.1:50051` 不可达
- `127.0.0.1:50060` 不可达
- 无 supported model credential
- 无 official release directory
- 无 official verified episode metrics

因此环境状态为 **REAL_TONGSIM_NOT_AVAILABLE**，真实成绩、matched A/B、模型排名和 first-failure frequency 均为 **NOT VERIFIED**。Round 5 遵守停止条件，没有继续增加未经真实失败证明的离线规则，也没有修改生产决策逻辑。

## 当前实现不可重复建设的能力

- Counting：有界确定性 `OR(AND(...)) AND NOT` 与公开 Registry 计数。
- NPC：required/known/missing facts、ownership/dependency 和 information-gain 问题选择。
- Raven：本地 CNN 候选与公开特征规则验证/重排。
- Jigsaw：piece × cell 全局 assignment 与歧义拦截。
- Tidyroom：目标候选 confidence/source/evidence/direct-safe 与保守完成判断。
- ActionGuard：动作 schema、公开对象映射与参数检查。
- Postconditions：`SUCCESS / FAILURE / UNKNOWN`，不把缺证据当成功。
- FinishGuard：官方完成证据或所有初始目标均验证完成。
- Recovery：正常模型调用 → 短上下文重试 → 保守 fallback，次数有界。
- Loop detection：重复动作、无进展、预算/阶段控制和 first-critical-failure 记录。

除非 official verified episode 明确证明缺陷，不要重写或扩建上述模块。

## 可直接复制给下一位开发者的指令词

```text
你现在接手 TongSIM / 通用智能体挑战赛 Agent 的 Round 6。不要从零设计，也不要继续堆叠未经真实失败验证的自然语言规则。

可写成果仓库：
https://github.com/hoosh11161/baseline-agent

Round 5 来源仓库：
https://github.com/jackzhu119/baseline-agent

第一步：验证远端、权限和最新 main。读取：
- ROUND6_CONTINUATION_PROMPT.md
- OPTIMIZATION_ROUND_5_REPORT.md
- ROUND5_CONTINUATION_PROMPT.md
- OPTIMIZATION_ROUND_4_REPORT.md
- docs/ROUND4_WINDOWS_HANDOFF_GUIDE.md
- benchmark/round5_*
- 最近 30 条 Git 历史

记录 git rev-parse HEAD、git remote -v、git branch -vv。以实际可写仓库最新 main 为基线，创建 codex-optimization-round-6 并立即推送备份；禁止 force push。

固定使用 Python 3.12.14，先复现：
uv sync --python 3.12.14 --extra dev
uv run --python 3.12.14 python scripts/generate_pb2.py
uv run --python 3.12.14 python -m pytest -q
uv run --python 3.12.14 python -m compileall -q arenaagent scripts tests
uv run --python 3.12.14 python scripts/replay_episode.py examples/public_trace_example.json

预期 109 tests passed、compileall PASS、offline replay PASS。若不一致，先定位，不得叠功能。

Round 6 的唯一高优先级是建立真实官方评测闭环：
1. 在比赛 Windows 机器准备 official release，启动 task service 和 TongSIM proxy，使 127.0.0.1:50051 与 127.0.0.1:50060 可达。
2. 配置一个受支持的模型 credential，不得提交 key、token 或 .env。
3. 运行 scripts/preflight.py --release-dir "实际路径"，所有必要项通过后再执行 episode。
4. 冻结 Round 5 main 为 BEFORE，在相同任务、seed、模型、参数、次数下运行 Counting、Raven、Tidyroom、NPC、Jigsaw。
5. 保存 official episode metrics：success、score、steps、invalid actions、LLM/VLM calls、tokens、latency、retry、replan、termination reason、first critical failure 和 failure category。
6. 用 scripts/benchmark.py、failure_analyzer.py、model_benchmark.py 汇总；只统计 official verified episodes。
7. 只修复最高频、可复现的 first-critical-failure；为该真实缺陷增加 regression test，小提交并推送。
8. 在同一批 matched cases 上执行 AFTER。没有 official matched evidence 就不得宣称成绩提升。

校准顺序：
- Raven：用官方 crop 测原 CNN、规则层、组合排序的 Top-1/Top-K，再调融合权重。
- Tidyroom：记录实际 target surface、公开字段、placement height、结果与重复移动，再调 confidence。
- Jigsaw：校验真实坐标轴、格心容差、rotation 与 assignment。
- NPC / Counting：只修真实回合暴露的解析问题。

证据边界：不得读取隐藏 ground truth，不得硬编码 seed/答案，不得修改官方协议，不得把 UNKNOWN 当 SUCCESS，不得把 synthetic/mock 结果混入 official score。

若真实服务、release、credential 或 official cases 仍缺失，立即标记 REAL_TONGSIM_NOT_AVAILABLE；不要改生产策略。交付新的 preflight 证据和精确阻塞项后停止。

最终创建 OPTIMIZATION_ROUND_6_REPORT.md 与 ROUND7_CONTINUATION_PROMPT.md，写明起止 SHA、真实环境、files、tests before/after、replay、matched A/B、VERIFIED/NOT VERIFIED、失败实验、first-failure frequency、Top 3 risks。分支推送后仅在 fast-forward 安全且关键测试通过时合并可写 main，绝不 force push。
```

## 下一轮最值得解决的三个问题

1. **真实官方评测闭环**：没有它就无法知道任何策略改动是否真正增分。
2. **Raven 官方图片域迁移**：必须用官方 crop 测量 CNN/规则融合，而不是继续凭合成题调权重。
3. **Tidyroom 目标表面与放置几何**：必须从真实成功/失败动作校准 surface、height、目标语义和防重复移动。

## 停止条件

如果没有真实服务、official release、模型凭据或 official verified episodes，不得以更多离线规则冒充优化；只提交可复现证据、明确阻塞项和 `NOT VERIFIED`。
