# Optimization Round 2 Report

## 1. Scope and verification boundary

This round starts from commit `296bbec` on branch
`codex-optimization-round-2`. It preserves the existing competition runtime,
task router, solvers, guards, and official protocols.

- **REAL_TONGSIM_NOT_AVAILABLE**: ports 50051/50060 and official scored
  episodes remain unavailable.
- **UNIT_TEST_VERIFIED**: 68 tests pass.
- **REPLAY_VERIFIED**: the supplied public-trace guard replay passes.
- No real success-rate or score improvement is claimed.

## 2. Problems found

### Counting union queries were misclassified

A query such as “红色或蓝色物体总共有多少” contains two values of the same
field but requests one total. The previous solver treated any same-field
alternatives as grouped output, returned no answer, and unnecessarily fell
back to the VLM. Its matching function also used AND between `color=Red` and
`color=Blue`, which no object can satisfy.

### Movable Jigsaw pieces polluted occupancy inference

The grid solver considered every object inside `reference_bounding` occupied,
including the subject-provided `piece_object_id` that still needed placement.
This could hide the real missing cell and derive the placement plane from an
unplaced piece.

### Jigsaw rotation did not react to verified failures

Although the prompt exposed `[0, 90, 180, 270]`, every inferred piece always
recommended yaw 0. Failed attempts did not advance to another finite rotation.

### Strategy refresh happened before placement verification

`TaskStrategyRouter.observe` ran before the hand/placement tracker processed
the latest observation. A failure detected in the current step therefore left
the current prompt with the previous rotation attempt for one extra turn.

## 3. Changes

- `arenaagent/competition/solvers/counting.py`
  - Explicit group words such as “分别/各有/each/respectively” select grouped
    output.
  - Multiple accepted values in one field now use OR; different fields still
    use AND.
  - One-total alternative queries now return a deterministic union count and
    bypass the VLM.
- `arenaagent/competition/solvers/jigsaw.py`
  - Exclude subject-provided movable piece IDs from occupied-cell and X-plane
    evidence.
  - Convert per-piece verified failure counts into bounded yaw attempts
    `0 -> 90 -> 180 -> 270 -> 0`.
  - Expose `rotation_attempt` in structured strategy context.
- `arenaagent/competition/task_router.py`
  - Pass tracker retry counts into Jigsaw inference.
- `arenaagent/vlm_agent/vlm_agent.py`
  - Refresh task strategy after hand/pick/place verification, so a failure
    changes the same-turn prompt immediately.
- Tests add union/OR-then-AND Counting cases, movable-piece exclusion, bounded
  rotation cycling, and an integration proof of same-turn Jigsaw rotation.

## 4. Test results

```text
uv run python -m pytest -q
68 passed

uv run python -m compileall -q arenaagent scripts tests
PASS

uv run python scripts/replay_episode.py examples/public_trace_example.json
PASS / OFFLINE_PUBLIC_TRACE_GUARD_REPLAY
```

Targeted Ruff format/check passed for the changed solver/router/test files.

## 5. Benchmark before and after

- `benchmark/before_round_2.json`: `NOT_VERIFIED`, 0 official episodes.
- `benchmark/after_round_2.json`: `NOT_VERIFIED`, 0 official episodes.
- All official failure-category counts remain unavailable. Empty frequencies
  mean no official data, not zero real failures.

## 6. VERIFIED

- Explicit grouped Counting remains grouped.
- Alternative values requesting one total use a deterministic union.
- Same-field alternatives combine with other attributes as OR-then-AND.
- An unplaced Jigsaw piece inside the board bounds does not occupy a cell or
  define the placement plane.
- Verified retry counts advance through four finite yaw candidates.
- A placement failure updates the Jigsaw rotation before the same-turn model
  prompt.
- Existing action, finish, loop, model recovery, Tidyroom, NPC, Raven, JSON,
  replay, and benchmark regressions remain green.

## 7. NOT VERIFIED

- Official Counting wording and answer formats beyond numeric totals.
- Jigsaw rotation correctness and coordinate tolerance in TongSIM.
- Raven accuracy on official images.
- NPC minimum-turn performance and deterministic final-answer serialization.
- Real success, score, steps, invalid actions, calls, tokens, and retries.

## 8. Remaining top three score risks

1. No official matched episodes exist to rank failures by real frequency.
2. Jigsaw/Tidyroom physical semantics remain simulator-dependent despite
   stronger offline state and spatial guards.
3. NPC planning, multi-group answer serialization, and Raven official accuracy
   remain unbenchmarked.

## 9. Next recommendation

Run official matched cases and retain public observations plus first-failure
artifacts. If official data is still unavailable, the next safe offline target
is NPC required-fact extraction and information-gain question ranking, without
hard-coding answers or names.
