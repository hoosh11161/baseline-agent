# TongSIM Competition High-Score Engineering Report

## 1. Verification boundary

This round improves the current `competition-optimization` branch without changing the official protobuf definitions, gRPC method names, `AgentBase` public lifecycle, `update_action` payload format, or competition action schema.

Status definitions used throughout this report:

- **VERIFIED**: executed on this machine with inspectable output.
- **NOT VERIFIED**: requires the official TongSIM client/task service or a configured model endpoint, neither of which is available in this environment.

| Item | Result | Status |
|---|---|---|
| Python source/import/compile | Python 3.12.14; imports and `compileall` pass | VERIFIED |
| Offline regressions | 57 tests pass | VERIFIED |
| Public-trace guard replay | Example replay passes; invented object ID is blocked | VERIFIED |
| Raven engineering path | Supplied checkpoint loads on CPU and returns 512 ranked candidates | VERIFIED |
| Raven task accuracy | No official Raven screenshots/results available | NOT VERIFIED |
| Five-task success/score | No official episodes exist locally | NOT VERIFIED |
| Model A/B selection | 63 configured model classes are discoverable, but no credentials/official episodes exist | NOT VERIFIED |
| Official result package | The five official result files and official release runner are absent | NOT VERIFIED |

`REAL_ENV_NOT_AVAILABLE` applies to score claims. No percentage improvement or “near-perfect” accuracy is claimed.

## 2. Preserved baselines

- Original supplied baseline: tag `baseline-original`, commit `3cfe5dfb7c7764d8575eaf87c733ee8cd0e941c6`.
- Start of this high-score solver round: tag `high-score-round-baseline`, commit `c08884c9a1cb2787fa84d86298f765558d695829`.
- The current branch consists of small task-by-task commits so any regression can be bisected or reverted independently.

## 3. Current architecture

```text
Official subject + public perception + public action result
                         |
                         v
                    Task Router
       +----------+------+------+------+----------+
       |          |             |             |   |
   Counting     Raven       Tidyroom         NPC Jigsaw
   registry     local       verified state  facts spatial grid
   + scan       model       machine          memory inference
       +----------+------+------+------+----------+
                         |
                         v
           Compact Episode / World State
                         |
                         v
       Shared ActionGuard + FinishGuard + LoopGuard
                         |
           valid --------+-------- invalid
             |                      |
             v                      v
        TongSIM API          one bounded repair /
             |               explicit recovery state
             v
     Result + next public observation verification
                         |
                         v
       Metrics / first-failure report / replay / training export
```

The generic VLM is no longer the sole planner for every task. Counting and Raven have direct deterministic/model-backed paths; Tidyroom, NPC, and Jigsaw receive task-specific structured state while retaining the official action handlers.

## 4. Modified files

Key implementation groups relative to `high-score-round-baseline`:

- Shared runtime and routing:
  - `arenaagent/competition/runtime.py`
  - `arenaagent/competition/task_router.py`
  - `arenaagent/vlm_agent/vlm_agent.py`
  - `arenaagent/preliminary_baseline_agent/preliminary_baseline_agent.py`
- Task solvers:
  - `arenaagent/competition/solvers/counting.py`
  - `arenaagent/competition/solvers/raven.py`
  - `arenaagent/competition/solvers/tidyroom.py`
  - `arenaagent/competition/solvers/npc.py`
  - `arenaagent/competition/solvers/jigsaw.py`
- Raven integration:
  - `arenaagent/vlm_agent/raven_skill.py`
  - `arenaagent/vlm_agent/skills/raven.py`
- Prompt/configuration:
  - `arenaagent/preliminary_baseline_agent/prompts/task_spec_prompt.json`
  - `arenaagent/vlm_agent/prompts/react.txt`
  - `arenaagent/vlm_agent/prompts/instructions.txt`
  - `arenaagent/vlm_agent/prompts/interaction_info.txt`
  - `config.toml.example`
- Evaluation loop:
  - `arenaagent/competition/replay.py`
  - `scripts/benchmark.py`
  - `scripts/compare_benchmarks.py`
  - `scripts/model_benchmark.py`
  - `scripts/failure_analyzer.py`
  - `scripts/replay_episode.py`
  - `scripts/run_model_matrix.ps1`
- Regression coverage:
  - `tests/test_counting_solver.py`
  - `tests/test_raven_solver.py`
  - `tests/test_tidyroom_state.py`
  - `tests/test_npc_memory.py`
  - `tests/test_jigsaw_solver.py`
  - `tests/test_replay_and_failure_analyzer.py`
  - existing runtime/integration/benchmark tests were extended.

Generated benchmark snapshots under `benchmark/` are committed so the absence of official data is itself auditable.

## 5. Five task strategies

### Counting

- Performs a bounded configurable scan (`counting_scan_degrees`) before submission.
- Maintains an episode registry with ID, semantic attributes, public position, first/last seen step, source IDs, count marker, and confidence.
- Uses the current mapped `object_id` as the primary identity.
- Uses semantic identity plus public spatial proximity only as a secondary remapped-ID match; distant similar objects remain separate.
- Python parses filters, groups and counts. A confident single count is submitted without a VLM call.
- Multi-group counts are computed deterministically but are not auto-submitted until official evaluator output formatting is observed; guessing that format could lose points.

### Raven

- Routes directly to the supplied `Resnet18_MLP_epoch_199.pth` solver, bypassing generic embodied-action prompting.
- Preserves 512 ranked triples, scores, top confidence, margin and a low-confidence flag.
- Caches one inference result and allows at most three ranked candidate attempts.
- A current synthetic CPU smoke test returned 512 candidates. This verifies the code/checkpoint path, not Raven accuracy on official images.

### Tidyroom

- Tracks `DISCOVERED -> TARGET_IDENTIFIED -> APPROACHING -> PICKED -> MOVING -> PLACED -> VERIFIED`.
- Confirms pickup and placement using the next public hand-state observation.
- Tracks completed, failed, current, pending and retried objects; verified objects cannot be picked again.
- Allows placement coordinates only from public `place_location` or computed AABB top/center evidence.
- Finish is blocked while an object is held, a transition is pending, known objects remain, or no completion evidence exists.

### NPC

- Converts replies into structured people locations, object locations, requirements, unresolved questions and the last answer.
- Normalizes questions and blocks duplicate questions that already have answers.
- Enforces the official subject-provided `npc_asset_name` allowlist and normalizes known aliases before validation.
- Does not hardcode dialogue answers.

### Jigsaw

- Uses `reference_bounding`, public object positions and optional row/column counts to infer grid centers and missing cells.
- Infers the placement X plane from the median of observed public piece coordinates. If no public X evidence exists, it deliberately withholds a full placement coordinate.
- Exposes only legal candidate yaw values `[0, 90, 180, 270]`; it does not auto-send an unverified placement.
- Uses the same pickup/place verification and FinishGuard as Tidyroom.

## 6. Shared guards, memory and recovery

ActionGuard checks before any TongSIM call:

1. action belongs to the implemented official-handler allowlist;
2. required parameters and types are valid;
3. object IDs are in the current public visible mapping;
4. NPC names are allowed by the official subject mapping;
5. placement is impossible with empty hands;
6. completed objects are not handled again;
7. repeated or repeatedly failed action signatures are blocked;
8. terminal actions match the task and pass task-specific completion checks.

For one invalid VLM action, the agent may make exactly one bounded repair call. The blocked action is never sent to TongSIM. Repeated actions, repeated failures or stagnant observations switch prompt state to `RECOVERY`, requiring the current micro-plan to be discarded and a different legal observation/subgoal/action to be chosen.

Episode changes clear conversation history, action history, object registry, NPC memory, Raven caches and recovery state. Prompts receive compact relevant state rather than the entire episode transcript.

## 7. Code-level conclusions for the ten requested risks

| Risk | Current conclusion | Status |
|---|---|---|
| Raven prompt was empty/weak | Raven bypasses the generic VLM and uses a structured local solver result | VERIFIED in code/tests; accuracy NOT VERIFIED |
| Counting prompt was empty/weak | Bounded scan, registry and deterministic counting are implemented | VERIFIED offline; coverage quality NOT VERIFIED |
| Preliminary agent depended on one generic VLM | Runtime task routing is authoritative; Counting/Raven bypass it, other tasks use structured strategy state | VERIFIED |
| Client failure returned `finish_task` | Client now returns an explicit error after bounded retries; the episode records a recoverable model failure | VERIFIED |
| Visible objects were only shown to VLM | IDs feed the registry and ActionGuard; a hallucinated ID is blocked before TongSIM | VERIFIED |
| Pick/put result was assumed | Pending pickup/placement must be confirmed by next hand state | VERIFIED offline |
| Seen objects were not retained | Registry persists and deduplicates objects within the episode | VERIFIED offline |
| Repeated actions could loop | Signature guard, failure blacklist, stagnation tracking, bounded repair and RECOVERY context exist | VERIFIED offline |
| `finish_task` could be premature | Task-specific FinishGuard blocks incomplete behavior tasks and wrong terminal actions | VERIFIED offline |
| Jigsaw fixed coordinates could overfit | Grid and X plane come from public evidence; absent evidence produces no full coordinate | VERIFIED offline; real layouts NOT VERIFIED |

## 8. Tests

The full suite covers the explicitly requested areas:

- counting registry, stable-ID deduplication, position-aware remapping, duplicate observations, grouped classes, attributes, empty scenes and bounded scanning;
- action schema, invalid object ID, unsupported actions, hand state and integration proof that invalid IDs do not reach TongSIM;
- repeated-action loop detection, failed-action blacklist, explicit recovery context and new-episode reset;
- FinishGuard and verified Tidyroom state transitions;
- NPC allowlist, normalized duplicate questions and structured fact extraction;
- Raven structured confidence/margin and bounded ranked attempts;
- Jigsaw grid inference, no case coordinates and no invented X plane;
- JSON recovery, model failure recovery, perception failure recovery and one bounded action repair;
- benchmark verification boundaries, public-trace replay and official-only failure analysis.

Commands and latest result:

```powershell
uv run python -m pytest -q
# 57 passed

uv run python -m compileall -q arenaagent scripts tests
uv run python -m ruff check arenaagent\competition scripts\benchmark.py `
  scripts\compare_benchmarks.py scripts\failure_analyzer.py `
  scripts\model_benchmark.py scripts\replay_episode.py tests
```

The new competition/evaluation modules pass targeted Ruff checks. A full-repository Ruff scan still reports 155 legacy style/complexity findings, concentrated in the supplied baseline utilities and Raven research file; it is not represented as a clean full-repository lint result.

## 9. Real benchmark results

| Task | Baseline success/score | Optimized success/score | Status |
|---|---|---|---|
| Tidyroom | — | — | NOT VERIFIED |
| Counting | — | — | NOT VERIFIED |
| NPC | — | — | NOT VERIFIED |
| Raven | — | — | NOT VERIFIED |
| Jigsaw | — | — | NOT VERIFIED |

Evidence:

- `127.0.0.1:50051` task service is not reachable.
- `127.0.0.1:50060` TongSIM proxy is not reachable.
- no supported model API-key environment variable is configured;
- no official episode metrics exist.

Therefore `benchmark/high_score_comparison/comparison.md` correctly says `NOT_VERIFIED` and makes no percentage claim.

## 10. Model comparison

`--get_vlm_model` currently discovers 63 configuration classes. Names alone are not evidence of quality. `scripts/run_model_matrix.ps1` and `scripts/model_benchmark.py` compare only official-service verified episodes by task on success, score, steps, invalid actions, latency and tokens.

Current model-comparison result: `NOT_VERIFIED / REAL_ENV_NOT_AVAILABLE`. No winning model has been selected.

## 11. Failure analyzer

The analyzer accepts only episodes with:

```text
verified = true
termination_reason = evaluated_by_official_task_service
```

It ranks the required failure taxonomy and proposes the next fix from the highest-frequency real category. Current output is `NOT_VERIFIED` because there are no official failed episodes; it does not turn synthetic failures into leaderboard evidence.

## 12. How to run locally

```powershell
cd C:\path\to\competition-agent
Copy-Item .\config.toml.example .\config.toml
uv sync --extra dev
uv run python scripts\generate_pb2.py
uv run python -m pytest -q
uv run python scripts\preflight.py --release-dir "C:\path\to\official\release"
uv run python -m arenaagent.builder --get_vlm_model
```

Set the API key required by the selected configured provider in the current PowerShell session. Do not write it into the repository.

Run the public-trace guard replay:

```powershell
uv run python scripts\replay_episode.py examples\public_trace_example.json
```

## 13. How to run a real TongSIM A/B test

1. Start the official Windows client/task service and confirm ports `50051` and `50060`.
2. Use the same official case set/order and run count for both snapshots. If the official runner has no seed control, retain task IDs and compare matched cases; do not call unmatched runs an A/B test.
3. Run the baseline from a separate worktree:

```powershell
git worktree add ..\competition-agent-baseline high-score-round-baseline
cd ..\competition-agent-baseline
Copy-Item .\config.toml.example .\config.toml
.\scripts\run_preliminary.ps1 -Model VLMGPT5Config -RunTimes 5
uv run python scripts\benchmark.py --output-dir benchmark\official_baseline
```

4. Run the optimized branch with the same settings:

```powershell
cd ..\competition-agent
.\scripts\run_preliminary.ps1 -Model VLMGPT5Config -RunTimes 5
uv run python scripts\benchmark.py --output-dir benchmark\official_optimized
uv run python scripts\failure_analyzer.py
```

5. Compare only after both JSON files report `VERIFIED`:

```powershell
uv run python scripts\compare_benchmarks.py `
  --baseline benchmark\official_baseline\benchmark_after.json `
  --optimized benchmark\official_optimized\benchmark_after.json `
  --output-dir benchmark\official_comparison
```

6. For model selection, use the official environment:

```powershell
.\scripts\run_model_matrix.ps1 `
  -Models @("VLMGPT5Config", "VLMGPT410414Config", "VLMQwen3VLPlus") `
  -RunTimes 3
```

7. Export training data only after official evaluation callbacks have produced verified episodes:

```powershell
uv run python scripts\export_verified_trajectories.py
```

8. After the five official runs are complete, invoke the official release's packaging command from its own release directory:

```powershell
.\start_test.bat package-results
```

Confirm that the official tool reports all five result files before submitting `arena_offline\result_package.bin`.

## 14. Remaining failure modes and opportunities

1. Run matched official episodes first; this unlocks real failure-frequency optimization and prevents tuning to synthetic assumptions.
2. Calibrate Tidyroom placement height/container behavior and Jigsaw rotation/verification from public observations in failed official seeds.
3. Confirm the official evaluator's exact multi-group Counting and NPC answer formatting, then replace the remaining VLM formatting fallback with deterministic serialization.
4. Benchmark model configurations per task rather than selecting one global model by name.
5. Validate Raven crop coordinates and confidence calibration on official screenshots; retain the current bounded fallback unless real evidence supports a change.

## 15. The three issues currently limiting leaderboard score most

Ordered by available evidence:

1. **No official runtime results exist.** This is the strongest verified constraint: both services are unreachable, credentials are absent, and every task benchmark has zero official episodes. Real failure frequency and score improvement cannot yet be measured.
2. **Physical placement semantics remain uncalibrated.** Offline logic prevents invented coordinates and verifies hand transitions, but Tidyroom surface/container behavior and Jigsaw rotations have not been exercised against the simulator. These tasks have the greatest residual environment-dependent action risk.
3. **Answer/model choices are unbenchmarked.** Multi-group Counting/NPC output formatting, Raven accuracy on official crops, and the best VLM configuration remain unknown without official cases and credentials.

The code is materially safer and more task-specific than the preserved baseline, but a “near-perfect competition model” can only be established after the official A/B loop produces verified evidence.
