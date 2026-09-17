# TongSIM Agent Round 7 Continuation Prompt

## Baseline

- Repository: `https://github.com/hoosh11161/baseline-agent`
- Round 6 branch: `codex-optimization-round-6`
- Round 6 starting production state: `34492df78f19c67248ac43eff8675464f108bf71`
- Use the actual latest `main` SHA when starting Round 7.

Round 6 reproduced 109 passing tests, successful compilation, and a passing offline replay. It again found no model credential, no official release, no service on ports 50051/50060, and no official verified episodes. Its status is `REAL_TONGSIM_NOT_AVAILABLE`; no production strategy was changed.

## Copyable Round 7 instructions

```text
Continue the TongSIM competition agent from the latest main of:
https://github.com/hoosh11161/baseline-agent

Read ROUND7_CONTINUATION_PROMPT.md, OPTIMIZATION_ROUND_6_REPORT.md, ROUND6_CONTINUATION_PROMPT.md, OPTIMIZATION_ROUND_5_REPORT.md, and the latest benchmark/round6_* artifacts before changing code.

Create codex-optimization-round-7 from the latest writable main and push the branch immediately. Record the exact starting SHA and remotes. Never force push.

Use Python 3.12.14. Reproduce pytest, compileall, public-trace replay, and preflight. The expected local baseline is 109 passing tests.

The only authorized optimization trigger is an official verified episode showing a reproducible failure. First obtain all four prerequisites:
1. official release directory;
2. reachable task service at 127.0.0.1:50051;
3. reachable TongSIM proxy at 127.0.0.1:50060;
4. a supported model credential provided through environment variables.

Freeze the starting commit as BEFORE. Run matched Counting, Raven, Tidyroom, NPC, and Jigsaw cases with identical tasks, seeds, model, parameters, and repetitions. Save official metrics and rank first-critical failures with the existing scripts.

Fix only the highest-frequency reproducible root cause. Add a focused regression test, run the full suite, commit and push. Repeat the exact cases as AFTER. Claim improvement only from official verified metrics.

Calibration priority after real evidence exists:
- Raven official crop Top-1/Top-K and CNN/rule blending;
- Tidyroom target surface, placement height, and repeated-object behavior;
- Jigsaw coordinate/rotation semantics;
- NPC or Counting only for parsing failures actually seen in official episodes.

Never read hidden ground truth, hard-code seeds or answers, change official protocols, commit credentials, treat UNKNOWN as SUCCESS, or mix synthetic results into official scores.

STOP CONDITION: if any prerequisite is missing or there are no official verified episodes, write REAL_TONGSIM_NOT_AVAILABLE, save exact preflight evidence, and do not change production strategy. Request the missing external inputs instead of creating another offline rule round.

Finish with OPTIMIZATION_ROUND_7_REPORT.md and ROUND8_CONTINUATION_PROMPT.md. Include start/end SHA, tests, replay, environment, matched A/B, VERIFIED/NOT VERIFIED, failures, risks, branch push, main merge, and clean-tree status.
```

## Required external inputs

Until the official release, live services, model credential, and verified episode metrics are available, further production optimization is blocked by evidence rather than by missing solver code.
