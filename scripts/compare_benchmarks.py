from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"benchmark must be a JSON object: {path}")
    return payload


def _index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("task_type")): row for row in payload.get("summary", []) if isinstance(row, dict)}


def build_comparison(baseline: dict[str, Any], optimized: dict[str, Any]) -> str:
    baseline_rows = _index(baseline)
    optimized_rows = _index(optimized)
    verified = baseline.get("status") == "VERIFIED" and optimized.get("status") == "VERIFIED"
    lines = [
        "# Benchmark Comparison",
        "",
        f"Status: **{'VERIFIED' if verified else 'NOT_VERIFIED'}**",
        "",
    ]
    if not verified:
        lines.extend(
            [
                "REAL_ENV_NOT_AVAILABLE: baseline or optimized results contain no official verified episodes.",
                "No percentage improvement is claimed.",
                "",
            ]
        )
    lines.extend(
        [
            "| Task | Baseline success | Optimized success | Baseline score | Optimized score |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for task_type in ("tidyroom", "counting", "npc", "raven", "jigsaw"):
        before = baseline_rows.get(task_type, {})
        after = optimized_rows.get(task_type, {})
        lines.append(
            f"| {task_type} | {before.get('success_rate')} | {after.get('success_rate')} | "
            f"{before.get('average_score')} | {after.get('average_score')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a non-fabricated baseline/optimized comparison.")
    parser.add_argument(
        "--baseline", type=Path, default=Path("benchmark/high_score_baseline/benchmark_after.json")
    )
    parser.add_argument(
        "--optimized", type=Path, default=Path("benchmark/high_score_current/benchmark_after.json")
    )
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/high_score_comparison"))
    args = parser.parse_args()
    baseline = _read(args.baseline)
    optimized = _read(args.optimized)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline_output = dict(baseline, snapshot="high-score-round-baseline")
    optimized_output = dict(optimized, snapshot="competition-optimization-current")
    (args.output_dir / "baseline.json").write_text(
        json.dumps(baseline_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (args.output_dir / "optimized.json").write_text(
        json.dumps(optimized_output, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    comparison = build_comparison(baseline, optimized)
    (args.output_dir / "comparison.md").write_text(comparison, encoding="utf-8")
    print(comparison)


if __name__ == "__main__":
    main()
