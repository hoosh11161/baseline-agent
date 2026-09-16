# Optimization Round 3 Report

## 1. Scope and verification boundary

This round starts from commit `db39b735` on branch
`codex-optimization-round-3`. It focuses on preventing malformed life-action
calls and reducing avoidable NPC interaction failures.

- **REAL_TONGSIM_NOT_AVAILABLE**: ports 50051/50060 and official scored
  episodes remain unavailable.
- **MODEL_CREDENTIALS_NOT_AVAILABLE**: live model evaluation was not run.
- **UNIT_TEST_VERIFIED**: 72 tests pass.
- **REPLAY_VERIFIED**: the supplied public-trace guard replay passes.
- No real success-rate or score improvement is claimed.

## 2. Problems found

### Implemented actions were absent from the model action schema

The runtime already handled observation, pointing, pouring, sitting, slicing,
washing, mopping, resting, and task completion, but `api_info.json` did not
describe them. The model therefore had no authoritative parameter schema for
several actions needed by operation tasks.

### Two-argument actions could pass validation with one argument missing

`pour_water` and `slice_food` both require an object ID and a location. The
runtime previously accepted a call missing either field, wasting a simulator
call before the lower-level handler rejected it.

### Official NPC asset IDs could fail the official-name guard

The task payload maps display names to asset IDs. If the model copied an
official asset ID such as `npc_zhao`, name normalization left it unchanged and
the allow-list rejected it, even though the value came from the official map.

### Polite rewording bypassed duplicate-question memory

Whitespace and punctuation were normalized, but harmless wrappers such as
“请问” and “你知道…吗” produced different keys. This allowed the agent to ask
the same NPC fact twice using slightly different phrasing.

## 3. Changes

- Added model-visible schemas for all primary implemented life/observation
  actions and `finish_task`.
- Added pre-dispatch validation requiring both object and location for
  `pour_water` and `slice_food`.
- Added reverse normalization from official NPC asset IDs to display names.
- Added conservative duplicate-question normalization for polite wrappers;
  distinct question content is not merged.
- Added four regression tests covering action schema completeness,
  two-argument validation, asset-ID normalization, and polite duplicates.

## 4. Verification

```text
uv run python -m pytest -q
72 passed

uv run python -m compileall -q arenaagent scripts tests
PASS

uv run python scripts/replay_episode.py examples/public_trace_example.json
PASS / OFFLINE_PUBLIC_TRACE_GUARD_REPLAY

uv run ruff check --select E,F <changed Python files>
PASS
```

Preflight imports and model assets pass. Official execution remains blocked by
missing model credentials, task service, TongSIM proxy, and release directory.

## 5. Benchmark before and after

- `benchmark/before_round_3.json`: `NOT_VERIFIED`, 0 official episodes.
- `benchmark/after_round_3.json`: `NOT_VERIFIED`, 0 official episodes.
- Empty failure frequencies mean no official data, not zero real failures.

## 6. VERIFIED

- Every primary runtime life/observation action has a prompt-visible schema.
- Incomplete pour/slice calls are rejected before reaching TongSIM.
- Valid pour/slice calls remain accepted when the object is visible.
- Official NPC asset IDs normalize to an allowed display name.
- Polite rewording of the same NPC question is blocked as a duplicate.
- Existing action, solver, replay, and benchmark regressions remain green.

## 7. NOT VERIFIED

- Real success, score, steps, invalid-action rate, calls, tokens, and retries.
- Exact simulator semantics for pouring, slicing, washing, mopping, and sitting.
- NPC answer quality and information-gain performance on official tasks.
- Raven and Jigsaw accuracy on official episodes.

## 8. Remaining top score risks

1. No matched official episodes exist to rank failures by real frequency.
2. NPC question planning is still model-led; only identity and duplicate guards
   are deterministic.
3. Physical action semantics remain simulator-dependent despite stronger
   schemas and local validation.
