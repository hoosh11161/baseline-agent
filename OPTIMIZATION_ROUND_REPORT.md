# Optimization Round Report

## 1. Verification boundary

This round started from `main` commit `21b6233` on branch
`codex-optimization-round-next`. The official task service (`127.0.0.1:50051`),
TongSIM proxy (`127.0.0.1:50060`), official release binaries, model credentials,
and official episode metrics were not available.

Therefore:

- **REAL_TONGSIM_NOT_AVAILABLE**
- **UNIT_TEST_VERIFIED**
- **REPLAY_VERIFIED** for the supplied public trace guard replay
- No real success-rate, score, step-count, or token improvement is claimed.

## 2. Code audit: current five-task handling

### Counting

`TaskStrategyRouter` runs a bounded configured turn scan, while
`CompetitionRuntime` accumulates a persistent object registry. Stable public
`object_id` is the primary identity; semantic fields plus a nearby public
position are used only when a perception ID changes. `CountingSolver` parses
known attributes and produces a deterministic Python count. A confident
single result is submitted without a VLM call. Multi-group output formatting
still falls back to the VLM because the official evaluator format is unknown.

### Raven

The generic VLM is bypassed. Raven task images are materialized and cropped,
then the supplied `Resnet18_MLP_epoch_199.pth` model returns 512 ranked answer
triples with confidence and margin metadata. Attempts are cached and limited
to three. The path is programmatic/model-backed, but it is not a symbolic
shape/count/orientation/fill/position/union/XOR solver and official Raven
accuracy is unverified.

### Tidyroom

The VLM selects actions using structured state, while a programmatic tracker
maintains `DISCOVERED -> TARGET_IDENTIFIED -> APPROACHING -> PICKED -> MOVING
-> PLACED -> VERIFIED`. Action success alone is not enough for pickup or
coordinate placement. Pickup needs a later held-object observation. After this
round, coordinate placement also needs a later, fresh public position near the
requested target (or official completion evidence); a stale pre-pick position
cannot verify it. Atomic put-in-container still uses the independent hand
release transition because that API exposes no container coordinate or ID.

### NPC

The VLM chooses the next question and final answer. Programmatic memory keeps
allowed people, normalized asked questions, replies, person/object locations,
requirements, unresolved questions, and recent facts. The guard rejects an
unknown NPC and repeated answered questions. Maximum-information-gain question
selection remains prompt-directed rather than deterministic.

### Jigsaw

`JigsawSpatialSolver` derives row/column centers and missing cells from
`reference_bounding`, declared dimensions, and public positions. It derives
the X plane only from observed public coordinates and exposes finite yaw
candidates `[0, 90, 180, 270]`. The VLM still chooses and executes placements;
real rotation semantics and layouts are unverified.

## 3. Ten most likely score-loss risks found

1. Coordinate placement was previously marked `VERIFIED` from an empty hand
   alone, even if the object was dropped at the wrong position. Fixed and
   covered by tests.
2. A stale pre-pick object position could be mistaken for post-placement
   evidence. Fixed with `position_seen_step` and covered by tests.
3. AABB surface placement used the raw surface top as the object center,
   risking intersection. Fixed by adding held-object half-height plus a small
   clearance.
4. Placement candidates included movable/finished objects, including the held
   object itself. Fixed by excluding task objects from target surfaces.
5. The planner could pick another object while the previous placement was
   still awaiting verification. Fixed by the action guard.
6. Historical user turns retained old base64 screenshots, increasing tokens
   and exposing stale IDs/images to the planner. Fixed; history is text-only.
7. Optional parameters such as `which_hand`, rotations, booleans, and
   `stop_distance` could reach handlers with invalid types. Fixed before the
   TongSIM call.
8. Multi-group Counting serialization remains evaluator-format dependent and
   VLM-mediated. Deterministic counts exist, but official formatting is not
   verified.
9. Raven crop compatibility and accuracy are unverified on official images;
   the supplied neural solver does not explicitly prove row-and-column rules.
10. NPC information-gain selection and Jigsaw final placement/rotation remain
    primarily VLM decisions, and repeated provider outages can still consume
    episode steps despite bounded client retries and retained state.

## 4. Evidence for requested risk questions

| Question | Audit conclusion | Evidence status |
|---|---|---|
| Which parts are programmatic? | Routing, registry/dedup, single Counting answers, Raven inference/ranking, state/memory/grid inference, guards, recovery state, metrics/replay | Code + unit verified |
| Which parts still rely on VLM/LLM? | Tidyroom target/action choice, NPC next question/final synthesis, Jigsaw placement/rotation, multi-group Counting formatting | Code verified; quality not verified |
| Invalid actions? | They can be proposed, but hallucinated IDs, unsupported/malformed actions, illegal hand/place state, duplicate questions, repeated actions, and newly checked optional types are locally blocked | Unit + replay verified; official frequency unavailable |
| Premature finish? | Task-specific FinishGuard exists; coordinate placements now remain pending until fresh spatial/official evidence | Unit verified |
| Duplicate/stuck loops? | Signature limits, failed-action blacklist, stagnant observation detection, bounded repair, and RECOVERY context exist | Unit verified |
| Model API failure ends episode? | No. Client retries are bounded; exhaustion returns an explicit recoverable failure, preserves world state, and now activates RECOVERY context instead of creating `finish_task` | Unit verified |
| Only designed, not truly validated? | Official five-task scores, physical placement tolerance, container correctness, Raven accuracy, NPC answer quality, multi-group format, Jigsaw rotations | NOT VERIFIED |

## 5. Modified files and reasons

- `arenaagent/competition/solvers/tidyroom.py`
  - Track the intended placement target and verification mode.
  - Require fresh public coordinate evidence for coordinate placement.
  - Reject wrong-position evidence and keep uncertain placement pending.
- `arenaagent/competition/runtime.py`
  - Record the step of fresh position evidence.
  - Exclude movable/completed objects from placement surfaces.
  - Add held-object half-height and clearance to AABB-top candidates.
  - Validate hand, rotation, boolean, and stopping-distance parameters.
  - Block a new pickup while a placement awaits verification.
  - Expose recent model/perception failures as RECOVERY without clearing state.
- `arenaagent/vlm_agent/vlm_agent.py`
  - Strip old image blocks before retaining history, while preserving text.
- `tests/test_tidyroom_state.py`
  - Add correct/wrong/stale placement, target exclusion, height, and pending
    placement guard regressions.
- `tests/test_competition_runtime.py`
  - Add optional parameter validation and model-failure recovery-state tests.
- `tests/test_agent_integration.py`
  - Add stale historical image removal coverage.
- `benchmark/before_this_round.json`, `benchmark/after_this_round.json`
  - Auditable snapshots with no invented official scores.

## 6. Tests and verification results

Commands executed:

```powershell
uv run python scripts/generate_pb2.py
uv run python -m pytest -q
# 63 passed

uv run python -m compileall -q arenaagent scripts tests
uv run python scripts/replay_episode.py examples/public_trace_example.json
# PASS / OFFLINE_PUBLIC_TRACE_GUARD_REPLAY
```

Targeted Ruff checks for the changed runtime/tracker/test files passed. The
pre-existing full `vlm_agent.py` file still has legacy complexity/style
findings unrelated to this change, so no full-repository lint-clean claim is
made.

A synthetic CPU smoke test loaded the supplied Raven checkpoint and returned
512 ranked triples. This verifies the executable checkpoint path, not task
accuracy.

## 7. Benchmark before and after

Both `benchmark/before_this_round.json` and
`benchmark/after_this_round.json` report:

- status: `NOT_VERIFIED`
- official verified episodes: `0`
- success/score/steps/invalid actions/model calls/tokens/retries: unavailable
- reason: no official task-service episode metrics were found

Required failure taxonomy counts from official verified failures:

| Category | Before | After |
|---|---:|---:|
| PERCEPTION | 0 | 0 |
| COUNT_DUPLICATION | 0 | 0 |
| PLANNING | 0 | 0 |
| INVALID_ACTION | 0 | 0 |
| NAVIGATION | 0 | 0 |
| PLACEMENT | 0 | 0 |
| NPC_REASONING | 0 | 0 |
| RAVEN_REASONING | 0 | 0 |
| JIGSAW_SPATIAL | 0 | 0 |
| JSON_PARSE | 0 | 0 |
| MODEL_API | 0 | 0 |
| LOOP | 0 | 0 |
| PREMATURE_FINISH | 0 | 0 |

These zeroes mean **no official data**, not zero real failures.

## 8. VERIFIED

- 63 offline tests pass.
- Counting dedup, action validation, FinishGuard, loop detection, NPC memory,
  Raven structured output, Jigsaw inference, JSON recovery, and model failure
  recovery retain coverage.
- Coordinate placement does not verify from API success or hand release alone.
- Wrong and stale placement positions do not complete an object.
- AABB placement height uses public held-object geometry.
- Old screenshot data is removed from retained model history.
- Public trace replay blocks an invented object ID before TongSIM.
- Raven checkpoint loads on CPU and produces ranked candidates.

## 9. NOT VERIFIED

- Real TongSIM success rate, score, steps, invalid-action rate, model calls,
  tokens, retries, and latency.
- Tidyroom/Jigsaw physical placement calibration in the official simulator.
- Raven correctness on official crops and rule families.
- Multi-group Counting answer format.
- NPC minimum-turn answer quality.
- Best model configuration or resilience under a real provider outage.

## 10. Remaining top three score-loss causes

1. No matched official episodes exist, so real failure frequency and score
   impact remain unknown.
2. Physical placement and Jigsaw rotation semantics are only offline-guarded,
   not simulator-calibrated.
3. NPC question choice, grouped answer formatting, and Raven official accuracy
   remain unbenchmarked reasoning/output risks.

## 11. Next-round recommendation

Run matched official Before/After episodes first. Preserve public observations,
action results, task IDs, model/token metrics, and first-failure artifacts.
Then prioritize the highest-frequency verified category. The first likely
calibration targets are placement tolerance/height, Jigsaw rotation retries,
and exact multi-group/NPC answer serialization.
