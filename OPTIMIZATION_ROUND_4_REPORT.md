# TongSIM Agent Optimization Round 4 Report

## Scope and provenance

- Upstream: `https://github.com/hoosh11161/baseline-agent`
- Delivery repository: `https://github.com/jackzhu119/baseline-agent`
- Branch: `codex-optimization-round-4`
- Starting commit: `2e391e52b9a6d84ea0c639ec678d6e0bd3d4d4d4`
- Ending implementation commit: `9c90974fbcc0cac37d93450a588fcf18ea621aad`
- Final documentation/evidence commit: recorded by Git after this report is committed
- Python used for verification: `3.12.14`

This report distinguishes local regression evidence from official competition evidence. No hidden answer, evaluation seed, ground truth, protocol modification, credential, or fabricated score is used.

## Environment and benchmark boundary

Final preflight found:

- Python, generated protobuf imports, and all three Raven assets: `PASS`
- Task service `127.0.0.1:50051`: `BLOCKED` (timeout)
- TongSIM proxy `127.0.0.1:50060`: `BLOCKED` (timeout)
- Supported model credentials: `BLOCKED` (none configured)
- Official release directory: `NOT_SUPPLIED`

Therefore the environment status is **REAL_TONGSIM_NOT_AVAILABLE**. There are zero official verified episodes. Real benchmark before/after, score change, success-rate change, model ranking, and leaderboard improvement are all **NOT VERIFIED**.

## Baseline and final verification

| Check | Before (`2e391e5`) | After (`9c90974`) | Meaning |
|---|---:|---:|---|
| Unit tests | 76 passed | 109 passed | 33 focused regressions added; all old tests retained |
| `compileall` | PASS | PASS | Python sources compile under 3.12.14 |
| Public trace replay | PASS | PASS | 0 expectation mismatches; not an official score |
| Official verified episodes | 0 | 0 | NOT VERIFIED |
| Real model matrix | unavailable | unavailable | NOT VERIFIED |
| Project-wide Ruff | not clean | 145 findings | Legacy lint debt remains; targeted Round 4 modules pass |

The final replay deliberately preserves one navigation postcondition as `UNKNOWN`; absent fresh public state change is not promoted to success.

## Implemented changes

### 1. NPC information-gain planner

- Added structured required, known, missing, ownership, location, requirement, dependency, asked, answered, and unresolved fact state.
- Added deterministic candidate-question ranking using information gain, task relevance, duplicate/already-known penalties, and estimated cost.
- Added owner-first multi-hop routing, redirect handling, semantic duplicate detection, direct evidence answers, and irrelevant-question rejection.

### 2. Physical postcondition verification

- Added `ActionExpectation` with explicit `SUCCESS`, `FAILURE`, and `UNKNOWN` results.
- Added public-evidence checks for pick, placement, navigation, and task-relevant state changes after pour/slice/wash/mop/sit operations.
- Integrated first-critical-failure capture and bounded replanning. `UNKNOWN` is never treated as successful completion.

### 3. Failure-driven and bounded recovery policy

- Expanded the first-failure taxonomy to cover perception, identity, query, duplicate counting, planning, action, navigation, pick, placement, physical postcondition, NPC, Raven, Jigsaw, JSON/model API, loops, premature finish, and budget exhaustion.
- Model recovery is bounded to normal call, shortened-context retry, and a conservative evidence-backed fallback.
- Added model failure, context size, prompt size, retry, replan, and postcondition metrics.
- Added step phases (`EARLY`, `MID`, `LATE`, `CRITICAL`) from real configured step limits; critical phases stop low-value exploration.

### 4. Counting boundary expressions

- Added bounded boolean filter evaluation as disjunctions of conjunctions with exclusions (`OR(AND(...)) AND NOT`).
- Covered “except/not”, grouped paired clauses, union versus separate counts, and supported public relational fields without cross-product overcounting.
- Uncertain language remains eligible for semantic fallback instead of silently producing an invented deterministic answer.

### 5. Verifiable Raven ranking

- Added public-panel features for component count, fill, centroid position, orientation, size, and horizontal/vertical symmetry.
- Added alternation, progression, sum, mean, union, intersection, difference, and XOR hypotheses.
- Verifies rules on two complete rows/columns, limits selection to 12 hypotheses, and records coverage, consistency, and complexity penalty.
- Rule evidence only reranks existing local ResNet18+MLP candidates; it adds no model call and leaves ranking unchanged when no rule is verified.

### 6. Jigsaw global assignment

- Added small global piece-to-cell assignment search instead of independent greedy placement.
- Scores public position/cell-center and rotation evidence, preserves coordinate tolerances, and exposes ambiguous candidate sets.
- Direct placement is disabled when multiple assignments remain equally plausible.

### 7. Tidyroom placement confidence and FinishGuard

- Placement candidates now carry source, confidence, evidence, selection margin, and `direct_safe`.
- Explicit `place_location` outranks AABB-derived surface estimates; tied high-confidence surfaces are treated as ambiguous.
- Conservative fallback observes again instead of placing on a low-confidence or ambiguous surface.
- Completion requires official completion evidence or verified completion of every initially declared object/piece. A single goal action cannot prove an unknown task is complete.

## Files changed

Production code:

- `arenaagent/competition/evaluation/__init__.py`
- `arenaagent/competition/evaluation/postconditions.py`
- `arenaagent/competition/runtime.py`
- `arenaagent/competition/task_router.py`
- `arenaagent/competition/solvers/counting.py`
- `arenaagent/competition/solvers/jigsaw.py`
- `arenaagent/competition/solvers/npc.py`
- `arenaagent/competition/solvers/raven.py`
- `arenaagent/competition/solvers/tidyroom.py`
- `arenaagent/vlm_agent/raven_skill.py`
- `arenaagent/vlm_agent/vlm_agent.py`
- `scripts/failure_analyzer.py`

Regression tests:

- `tests/test_agent_integration.py`
- `tests/test_competition_runtime.py`
- `tests/test_counting_solver.py`
- `tests/test_jigsaw_solver.py`
- `tests/test_npc_memory.py`
- `tests/test_postconditions.py`
- `tests/test_raven_solver.py`
- `tests/test_task_router.py`
- `tests/test_tidyroom_state.py`

Evidence and handoff:

- `benchmark/round4_before.json`
- `benchmark/round4_after.json`
- `benchmark/round4_preflight.json`
- `benchmark/round4_replay.json`
- `benchmark/round4_official/`
- `benchmark/round4_failure_analysis/`
- `benchmark/round4_model_comparison/`
- `docs/ROUND4_WINDOWS_HANDOFF_GUIDE.md`
- `OPTIMIZATION_ROUND_4_REPORT.md`

## Failed or blocked experiments

1. The default Python 3.14 environment attempted to build locked `tiktoken==0.8.0` with Rust and could not provide a clean setup. All verification was rerun with Python 3.12.14.
2. Real TongSIM A/B was blocked because 50051 and 50060 timed out and no official release was supplied.
3. A real model matrix was blocked because no supported model credential was present.
4. Project-wide Ruff remains red with 145 legacy findings. Round 4 targeted code checks pass, and the modified Raven adapter retains the same nine warnings present in its upstream form; this round does not claim global lint cleanup.

## First-failure frequency

Status: **NOT VERIFIED**.

- Official verified episodes: 0
- Official failed episodes with first-critical-error evidence: 0
- Ranked failure frequencies: unavailable

Synthetic/unit failures are intentionally not mixed into an official failure-frequency table.

## VERIFIED

- 109 unit tests pass.
- `compileall` passes.
- Public offline replay passes with zero mismatches.
- Round 4 behavior is backed by focused synthetic/mock regressions.
- Implementation commits were pushed incrementally to `origin/codex-optimization-round-4`.

## NOT VERIFIED

- Official task success rate and score.
- Any leaderboard improvement.
- Real model latency, token, validity, or task-result ranking.
- Raven performance on official screenshots.
- Tidyroom/Jigsaw physical coordinate semantics against a live simulator.

## Top three remaining score risks

1. **No live simulator/official episode evidence.** Both service ports timed out and there are zero official episodes, so action timing, returned field shapes, coordinate conventions, and end-to-end scoring remain the largest unmeasured risk.
2. **Raven domain transfer is unmeasured.** The new verifier passes synthetic rule cases, but official crops, rendering noise, rotations, and the pretrained model's real ranking accuracy were unavailable.
3. **Tidyroom target semantics remain only partially observable.** Confidence gating prevents unsafe automatic placement, but when several plausible surfaces are visible the public fields do not yet prove which surface satisfies the natural-language goal; the safe choice consumes observation steps.

## Next-round recommendations

1. Bring up the official client, task service, and proxy; freeze matched seeds/conditions and collect verified before/after episodes for all five task types.
2. Rank official first-critical failures and fix the highest-frequency class before adding more rules.
3. Build a small official Raven crop regression set and calibrate CNN/rule blending from measured accuracy.
4. Record real Tidyroom target/surface fields and placement outcomes, then calibrate confidence and target compatibility without hidden-state access.
5. Compare supported models only on identical verified inputs, including structured-output validity, latency, tokens, and final task result.

