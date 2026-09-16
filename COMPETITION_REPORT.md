# Competition Optimization Report

## Verification boundary

The source repository, Python 3.12 environment, generated gRPC clients, model assets, prompt rendering, deterministic Raven inference and offline regression suite were verified on Windows.

The official competition client and task-service binaries were not present on this machine. Therefore all real episode success rates and scores are **NOT VERIFIED**. No score in this report is estimated or fabricated.

## Baseline Performance

| Task | Success rate | Score | Steps | Status |
|---|---:|---:|---:|---|
| Tidy room | — | — | — | NOT VERIFIED |
| Counting | — | — | — | NOT VERIFIED |
| NPC | — | — | — | NOT VERIFIED |
| Raven | — | — | — | NOT VERIFIED |
| Jigsaw | — | — | — | NOT VERIFIED |

Baseline source is preserved by Git tag `baseline-original` at commit `3cfe5dfb7c7764d8575eaf87c733ee8cd0e941c6`. Machine-readable placeholders are in `benchmark/baseline_results.json` and `benchmark/benchmark_before.csv`.

## Current Performance

Real task performance remains **NOT VERIFIED** until ports `127.0.0.1:50051` and `127.0.0.1:50060` are provided by the official system. Once episodes run, each one writes a verified metrics artifact under `logs/metrics/`; `scripts/benchmark.py` generates `benchmark_after.csv` and `benchmark_after.json` from those artifacts.

Offline engineering verification:

- 19 unit/integration regressions passed.
- CLI model discovery passed.
- Generated protobuf imports passed after fixing the official generator's package-prefix bug.
- Raven checkpoint performed a real CPU forward pass and returned 512 ranked three-answer candidates.
- Invalid hallucinated object IDs were proven not to reach the TongSim client in an integration test.

## Biggest Improvements

1. Added strict pre-execution action validation for schemas, mapped object IDs, coordinates, hand state, terminal-action type, duplicate NPC questions and repeated-action loops.
2. Added compact world state with stable-ID object deduplication, grouped counts, observation diffs, NPC facts and step-budget phases.
3. Routed Raven directly to the supplied local checkpoint, avoiding an unnecessary VLM decision and preserving ranked retries.
4. Added safe, balanced JSON extraction with `ast.literal_eval` fallback; removed unsafe model-output `eval` execution.
5. Added episode metrics and failure reports with explicit verification status, first critical error and standard failure classes.
6. Replaced the long example-heavy generic prompt with a shorter schema-bound policy and task-specific strategies.
7. Fixed generated gRPC imports so the installed CLI starts without a top-level `arena` compatibility package.

## Failed Experiments / Environment Blocks

- `pip install uv` could not find a package from the configured Python index. `uv 0.12.14` was installed successfully with WinGet instead.
- `uv python install 3.12` downloaded Python successfully but reported a minor-version-link warning; the concrete Python 3.12.14 executable works and was used to build the environment.
- A real baseline A/B run could not start because the official client/task-service bundle is absent. This remains an environment block, not a passing result.

## Remaining Failure Modes

Frequency ordering is unavailable until official episodes exist. Highest-risk unverified areas are:

1. Tidy-room target-placement semantics and exact surface heights.
2. Jigsaw slot coordinates/rotations across unseen layouts.
3. Counting coverage when mapped IDs change or the task spans multiple viewpoints.
4. NPC answer formatting expected by the evaluator.
5. Raven crop-coordinate compatibility with actual competition screenshots.

## Top 5 Next Optimizations

1. Run the preserved baseline and optimized branch on the same official task seeds/runs; retain only measured improvements.
2. Use `failure_report.json` frequencies to fix the largest real failure class first.
3. Add deterministic counting submission only after real subject wording and ID stability are observed.
4. Fit tidy-room placement heuristics to public observations/action results, without hidden-state access or case hardcoding.
5. Add jigsaw edge/slot consistency scoring if real failures show the VLM placement policy is the dominant bottleneck.

## Reproduction

```powershell
uv sync --extra dev
uv run python scripts/generate_pb2.py
uv run python -m pytest -q
uv run python scripts/preflight.py --release-dir "C:\path\to\official\release"
.\scripts\run_preliminary.ps1 -Model VLMGPT5Config -RunTimes 5
uv run python scripts\benchmark.py
```

After the official runner finishes, use its own `start_test.bat package-results` command from the release directory to create `arena_offline/result_package.bin`. That packaging step cannot be truthfully completed without the official release bundle and its five result files.
