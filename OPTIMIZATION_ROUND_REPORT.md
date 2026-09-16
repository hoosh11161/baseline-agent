# Optimization Round 4 Report

## 1. Verification boundary

This round starts from `main` commit `2ecf483` on branch
`codex-optimization-round-4`. The official task service, TongSIM proxy, model
credentials, release package, and official scored episodes are unavailable.

- **REAL_TONGSIM_NOT_AVAILABLE**
- **UNIT_TEST_VERIFIED**: 76 tests pass.
- **REPLAY_VERIFIED**: the public trace guard replay passes.
- No real score or success-rate improvement is claimed.

## 2. Problem found

The Jigsaw solver correctly excluded movable pieces before placement, but it
continued excluding them after observation-verified placement. Consequently a
completed piece never became an occupied grid cell, the missing-cell list did
not shrink correctly, and later pieces could be paired with the wrong cell.

The solver also already produced a complete high-confidence position and
finite rotation for the held piece, but the agent still asked the VLM to copy
those values into an action. This added one model call and reintroduced JSON,
coordinate, and rotation transcription risk.

## 3. Modified files

- `arenaagent/competition/solvers/jigsaw.py`
  - Accept verified completed-piece IDs.
  - Treat verified pieces as occupied public board evidence.
  - Remove completed pieces from the remaining placement plan.
- `arenaagent/competition/task_router.py`
  - Pass tracker completion state into Jigsaw inference.
  - Directly propose `put_down_sth` only when the current piece is confirmed
    held and both plan and piece confidence are at least 0.8.
  - Keep the VLM fallback when coordinates, rotation, confidence, or held-piece
    identity are incomplete.
- `tests/test_jigsaw_solver.py`
  - Verify completed-piece occupancy and plan removal.
- `tests/test_task_router.py`
  - Verify high-confidence direct placement and low-evidence fallback.
- `tests/test_agent_integration.py`
  - Verify direct placement reaches TongSIM without a VLM call.
- `benchmark/round_4_before`, `benchmark/round_4_after`
  - Preserve exact benchmark JSON/CSV output.
- `benchmark/round_4_replay.json`
  - Preserve public-trace replay evidence.

## 4. Why this change

The change removes a proven state-consistency defect and makes an already
programmatic decision authoritative. It does not introduce fixed case
coordinates: placement still comes only from `reference_bounding`, declared
grid dimensions, public object positions, tracker verification, and the finite
rotation sequence. Low-confidence cases remain model-led.

## 5. Added tests

Four new tests cover:

1. completed-piece occupancy and plan removal;
2. valid direct placement for a confirmed held piece;
3. fallback when no public placement plane exists;
4. end-to-end proof that high-confidence placement uses zero VLM calls.

## 6. Test results

```text
uv run python -m pytest -q
76 passed

uv run python -m compileall -q arenaagent scripts tests
PASS

uv run ruff check <changed Python files>
PASS

uv run python scripts/replay_episode.py examples/public_trace_example.json
PASS / OFFLINE_PUBLIC_TRACE_GUARD_REPLAY
```

## 7. Benchmark before and after

Both exact snapshots report `NOT_VERIFIED` with zero official episodes:

- `benchmark/round_4_before/benchmark_after.json`
- `benchmark/round_4_after/benchmark_after.json`

All requested failure-frequency values are unavailable. Zero episodes and an
empty failure list mean no official data, not zero real failures.

## 8. VERIFIED

- A verified placed puzzle piece contributes an occupied grid cell.
- A verified piece is not planned for placement again.
- Remaining pieces are paired only with remaining missing cells.
- A confirmed held piece with complete high-confidence public geometry is
  placed through a locally generated, ActionGuard-validated action.
- That direct path does not call the VLM.
- Missing X-plane evidence and other incomplete plans still fall back safely.
- Existing Counting, Raven, Tidyroom, NPC, guard, recovery, and replay tests
  remain green.

## 9. NOT VERIFIED

- Real Jigsaw placement and rotation behavior in TongSIM.
- Official success, score, steps, invalid actions, model calls, tokens, retry
  counts, and latency.
- Jigsaw layouts without declared row/column counts on official cases.
- NPC information-gain quality, Raven accuracy, and grouped Counting output
  format on official tasks.

## 10. Remaining largest score risks

1. No official episode data exists to rank real failure frequency.
2. A placement that remains occluded after release can stay pending because
   there is no fresh coordinate evidence; bounded observation recovery needs
   official calibration.
3. NPC question choice and several Tidyroom life-action completion checks
   remain model- or simulator-response-dependent.

## 11. Next-round recommendation

Use official traces if available. Otherwise, the next safe offline target is a
bounded recovery policy for placements that remain pending without fresh
position evidence, ensuring it requests a changed viewpoint and eventually
replans without falsely marking the object complete.
