from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def load_episodes(metrics_dir: Path) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for path in sorted(metrics_dir.glob("episode_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            episodes.append(payload)
    return episodes


def summarize_models(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        metadata = episode.get("run_metadata") or {}
        model = str(metadata.get("model") or "unknown")
        task_type = str(episode.get("task_type") or "unknown")
        grouped[(model, task_type)].append(episode)

    rows: list[dict[str, Any]] = []
    for (model, task_type), group in sorted(grouped.items()):
        verified = [item for item in group if item.get("verified") is True]
        successes = [1.0 if item.get("success") is True else 0.0 for item in verified]
        rows.append(
            {
                "model": model,
                "task_type": task_type,
                "episodes": len(group),
                "verified_episodes": len(verified),
                "success_rate": _average(successes),
                "average_score": _average(
                    [float(item["score"]) for item in verified if isinstance(item.get("score"), (int, float))]
                ),
                "average_steps": _average([float(item.get("steps", 0)) for item in verified]),
                "average_invalid_actions": _average(
                    [float(item.get("invalid_actions", 0)) for item in verified]
                ),
                "average_latency": _average([float(item.get("latency", 0)) for item in verified]),
                "average_tokens": _average([float(item.get("tokens", 0)) for item in verified]),
                "status": "VERIFIED" if verified else "NOT_VERIFIED",
            }
        )
    return rows


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Model Benchmark",
        "",
        f"Status: **{payload['status']}**",
        "",
        "Only official task-service verified episodes may be used to choose a model.",
        "",
        "| Model | Task | Verified episodes | Success | Score | Steps | Invalid | Latency | Tokens |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {model} | {task_type} | {verified_episodes} | {success_rate} | {average_score} | "
            "{average_steps} | {average_invalid_actions} | {average_latency} | {average_tokens} |".format(**row)
        )
    if not payload["rows"]:
        lines.extend(["", "REAL_ENV_NOT_AVAILABLE: no episode metrics were found."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare models using official verified episode metrics only.")
    parser.add_argument("--metrics-dir", type=Path, default=Path("logs/metrics"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/model_comparison"))
    args = parser.parse_args()
    rows = summarize_models(load_episodes(args.metrics_dir))
    payload = {
        "status": "VERIFIED" if any(row["verified_episodes"] for row in rows) else "NOT_VERIFIED",
        "environment_status": "AVAILABLE" if rows else "REAL_ENV_NOT_AVAILABLE",
        "rows": rows,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "model_comparison.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(args.output_dir / "model_comparison.md", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
