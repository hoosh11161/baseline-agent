from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TASK_TYPES = ("tidyroom", "counting", "npc", "raven", "jigsaw", "unknown")
FIELDS = (
    "task_type",
    "episodes",
    "verified_episodes",
    "success_rate",
    "average_score",
    "average_steps",
    "median_steps",
    "invalid_action_rate",
    "stuck_rate",
    "average_llm_calls",
    "average_tokens",
    "average_retries",
    "average_latency",
    "repeated_actions",
    "finish_guard_blocks",
    "status",
)
MAX_FAILURE_EXAMPLES = 3


def load_episodes(metrics_dir: Path) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    for path in sorted(metrics_dir.glob("episode_*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            episodes.append(value)
    return episodes


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return round((ordered[middle - 1] + ordered[middle]) / 2, 6)


def summarize(episodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for episode in episodes:
        grouped[str(episode.get("task_type") or "unknown")].append(episode)

    rows: list[dict[str, Any]] = []
    task_types = [task_type for task_type in TASK_TYPES if task_type in grouped or task_type != "unknown"]
    for task_type in task_types:
        group = grouped.get(task_type, [])
        verified = [item for item in group if item.get("verified") is True]
        success_values = [
            1.0 if item.get("success") is True else 0.0 for item in verified if item.get("success") is not None
        ]
        scores = [float(item["score"]) for item in verified if isinstance(item.get("score"), (int, float))]
        steps = [float(item.get("steps", 0)) for item in group]
        invalid = sum(int(item.get("invalid_actions", 0)) for item in group)
        total_steps = sum(int(item.get("steps", 0)) for item in group)
        stuck_episodes = sum(1 for item in group if int(item.get("stuck_count", 0)) > 0)
        rows.append(
            {
                "task_type": task_type,
                "episodes": len(group),
                "verified_episodes": len(verified),
                "success_rate": _average(success_values),
                "average_score": _average(scores),
                "average_steps": _average(steps),
                "median_steps": _median(steps),
                "invalid_action_rate": round(invalid / total_steps, 6) if total_steps else None,
                "stuck_rate": round(stuck_episodes / len(group), 6) if group else None,
                "average_llm_calls": _average([float(item.get("llm_calls", 0)) for item in group]),
                "average_tokens": _average([float(item.get("tokens", 0)) for item in group]),
                "average_retries": _average([float(item.get("retries", 0)) for item in group]),
                "average_latency": _average([float(item.get("latency", 0)) for item in group]),
                "repeated_actions": sum(int(item.get("repeated_actions", 0)) for item in group),
                "finish_guard_blocks": sum(int(item.get("finish_guard_blocks", 0)) for item in group),
                "status": "VERIFIED" if verified else "NOT_VERIFIED",
            }
        )
    return rows


def failure_frequencies(episodes: list[dict[str, Any]], metrics_dir: Path) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for path in sorted(metrics_dir.glob("failure_*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        failure = report.get("first_critical_error") or {}
        error_type = str(failure.get("category") or failure.get("error_type") or "UNCLASSIFIED")
        counts[error_type] += 1
        if len(examples[error_type]) < MAX_FAILURE_EXAMPLES:
            examples[error_type].append(str(report.get("episode_id") or ""))
    return [
        {"error_type": name, "count": count, "example_episode_ids": examples[name]}
        for name, count in counts.most_common()
    ]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize official episode artifacts without inventing scores.")
    parser.add_argument("--metrics-dir", type=Path, default=Path("logs/metrics"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/current"))
    args = parser.parse_args()

    episodes = load_episodes(args.metrics_dir)
    rows = summarize(episodes)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "benchmark_after.csv", rows)
    payload = {
        "status": "VERIFIED" if any(row["verified_episodes"] for row in rows) else "NOT_VERIFIED",
        "reason": None if episodes else "No official task-service episode metrics were found.",
        "episodes": episodes,
        "summary": rows,
        "failure_frequencies": failure_frequencies(episodes, args.metrics_dir),
    }
    (args.output_dir / "benchmark_after.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
