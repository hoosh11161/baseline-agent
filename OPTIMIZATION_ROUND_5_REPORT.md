# TongSIM Agent Optimization Round 5 Report

## Scope and provenance

- Requested source repository: `https://github.com/jackzhu119/baseline-agent`
- Writable delivery repository for the authenticated GitHub identity: `https://github.com/hoosh11161/baseline-agent`
- Branch: `codex-optimization-round-5`
- Starting commit: `a20a67ff5b7f9f09a9a4bb552bc81cd033b83dee`
- Ending implementation commit: `a20a67ff5b7f9f09a9a4bb552bc81cd033b83dee` (no production behavior changed)
- Final documentation/evidence commit: recorded by Git after this report is committed
- Python used for verification: `3.12.14`

The branch was created from the latest `jackzhu119/main`. The initial push to that repository failed with HTTP 403 because the active GitHub identity is `hoosh11161`; the same branch was immediately backed up to the writable `hoosh11161/baseline-agent` fork. No force push was used.

This round obeyed the Round 5 stopping condition: without real services, a supported model credential, an official release, or verified official episodes, no additional offline language rules or unmeasured decision changes were added.

## Handoff and code audit

The following sources were read before any Round 5 change:

- `ROUND5_CONTINUATION_PROMPT.md`
- `OPTIMIZATION_ROUND_4_REPORT.md`
- `COMPETITION_HIGH_SCORE_REPORT.md`
- `COMPETITION_REPORT.md`
- `README.md`
- `docs/ROUND4_WINDOWS_HANDOFF_GUIDE.md`
- Round 4 benchmark, preflight, and replay evidence
- Recent Git history and the competition runtime, solvers, guards, recovery, and Raven integration

The implementation matches the Round 4 handoff: deterministic counting, NPC information-gain planning, Raven rule reranking, Jigsaw global assignment, confidence-gated Tidyroom placement, public-evidence postconditions, ActionGuard, FinishGuard, bounded model recovery, and loop detection are present and covered by the existing regression suite.

## Environment and benchmark boundary

Round 5 preflight found:

- Python 3.12.14: `PASS`
- Generated protobuf imports: `PASS`
- All three Raven assets: `PASS`
- Supported model credentials: `BLOCKED` (none configured)
- Task service `127.0.0.1:50051`: `BLOCKED` (timeout)
- TongSIM proxy `127.0.0.1:50060`: `BLOCKED` (timeout)
- Official release: `BLOCKED` (not supplied)

Environment status: **REAL_TONGSIM_NOT_AVAILABLE**.

There are zero official verified episodes. Official success rate, score, matched A/B change, first-failure frequency, real model comparison, and leaderboard improvement are therefore **NOT VERIFIED**.

## Baseline and final verification

| Check | Before | After | Meaning |
|---|---:|---:|---|
| Unit tests | 109 passed | 109 passed | Existing Round 4 behavior remains green |
| `compileall` | PASS | PASS | Python sources compile under 3.12.14 |
| Public trace replay | PASS | PASS | 0 expectation mismatches; not an official score |
| Official verified episodes | 0 | 0 | NOT VERIFIED |
| Real matched A/B | unavailable | unavailable | NOT VERIFIED |
| Real model matrix | unavailable | unavailable | NOT VERIFIED |

The replay includes one postcondition recorded as `UNKNOWN`. It is not promoted to success without new public evidence.

## Round 5 findings and changes

### Finding

The highest-priority blocker is not another missing offline rule. It is the absence of an official executable evaluation loop and first-critical-failure data. Changing Raven blending, Tidyroom target semantics, Jigsaw tolerances, or natural-language rules without matched official cases would create unmeasured behavior and violate the handoff's evidence boundary.

### Production behavior

No production decision logic was changed. The implementation SHA intentionally remains the Round 5 starting SHA.

### Reproducibility evidence added

- `benchmark/round5_baseline_preflight.json`
- `benchmark/round5_baseline_replay.json`
- `benchmark/round5_before/`
- `benchmark/round5_after/`
- `benchmark/round5_failure_analysis/`
- `benchmark/round5_model_comparison/`
- `OPTIMIZATION_ROUND_5_REPORT.md`
- `ROUND6_CONTINUATION_PROMPT.md`

The benchmark, failure-analysis, and model-comparison artifacts retain null/empty official results and `NOT_VERIFIED`; no synthetic result is mixed into an official score table.

## Benchmark before and after

- Before status: `NOT_VERIFIED`
- After status: `NOT_VERIFIED`
- Before official verified episodes: 0
- After official verified episodes: 0
- Measured score delta: unavailable
- Measured success-rate delta: unavailable

The before and after states are intentionally equivalent because the real evaluation prerequisite was unavailable and no production behavior was changed.

## Failed or blocked experiments

1. Push to `jackzhu119/baseline-agent` was rejected with HTTP 403 for the authenticated `hoosh11161` identity. The branch was pushed to `hoosh11161/baseline-agent` instead.
2. Real TongSIM A/B was blocked because ports 50051 and 50060 timed out and no official release directory was supplied.
3. Real model benchmarking was blocked because no supported API credential was configured.
4. Official first-critical-failure ranking was blocked because no official verified episodes or failures were available.
5. Raven and Tidyroom calibration was not attempted because no official screenshots, live placement outcomes, or matched cases were available.

## VERIFIED

- The branch started from `jackzhu119/main@a20a67f`.
- 109 unit tests pass under Python 3.12.14 before and after the Round 5 evidence work.
- `compileall` passes.
- Public offline replay passes with zero expectation mismatches.
- Python, protobuf imports, and Raven assets pass preflight.
- The existing Round 4 implementation remains unchanged.

## NOT VERIFIED

- Official task success rate and score.
- Any leaderboard improvement.
- Real model structured-output validity, latency, token use, or final task result.
- Raven accuracy on official screenshots.
- Tidyroom surface selection, placement height, and target semantics in the live simulator.
- Jigsaw coordinate, grid-center, and rotation behavior in official episodes.

## First-failure frequency

Status: **NOT VERIFIED**.

- Official verified episodes: 0
- Official verified failures: 0
- Ranked first-critical failures: unavailable

## Top three remaining score risks

1. **No live official feedback loop.** Service schemas, action timing, coordinate conventions, completion signals, and final scoring have not been observed end to end.
2. **Raven domain transfer is unmeasured.** The CNN/rule blend is backed only by local assets and synthetic regressions, not an official image set with measured Top-1/Top-K accuracy.
3. **Tidyroom target semantics and placement geometry are uncalibrated.** Public fields may expose several plausible surfaces, while correct height, target compatibility, and repeated-object handling require live outcome evidence.

## Round 6 recommendations

1. Run `scripts/preflight.py` on the competition Windows machine with the real release directory, both services running, and a supported model credential.
2. Freeze this commit as BEFORE; collect identical task/seed/model/parameter episodes for all five task types and save official metrics.
3. Rank first-critical failures from those episodes and fix only the highest-frequency reproducible root cause.
4. Calibrate Raven CNN/rule ranking on official crops and Tidyroom surface/height confidence on verified live placements.
5. Repeat the exact matched cases as AFTER, keep raw evidence, and claim improvement only when the official metrics support it.

## Minimum command set for the competition machine

```powershell
uv sync --python 3.12.14 --extra dev
uv run --python 3.12.14 python scripts/generate_pb2.py
uv run --python 3.12.14 python scripts/preflight.py --release-dir "C:\path\to\official-release" --output benchmark/round6_preflight.json
uv run --python 3.12.14 python -m pytest -q
uv run --python 3.12.14 python scripts/benchmark.py --metrics-dir "C:\path\to\official-metrics" --output-dir benchmark/round6_before
uv run --python 3.12.14 python scripts/failure_analyzer.py --metrics-dir "C:\path\to\official-metrics" --output-dir benchmark/round6_failure_analysis
uv run --python 3.12.14 python scripts/model_benchmark.py --metrics-dir "C:\path\to\official-metrics" --output-dir benchmark/round6_model_comparison
```

Required inputs are the official release path, reachable services at 50051 and 50060, one supported model credential, and official episode metric JSON files produced under matched conditions.
