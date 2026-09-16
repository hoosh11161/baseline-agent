from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from arenaagent.competition.training_data import OFFICIAL_TERMINATION

RECOMMENDATIONS = {
    "PERCEPTION": "Inspect visibility changes and object-ID mapping before changing the planner.",
    "OBJECT_ID": "Inspect the first invalid visible-ID mapping and refresh perception before object actions.",
    "COUNTING_QUERY": "Inspect the parsed boolean filter expression and fall back when query semantics are uncertain.",
    "COUNT_DUPLICATION": "Tune position-aware deduplication using public observations from the failed seeds.",
    "PLANNING": "Inspect the first wrong subgoal and add a deterministic task-state transition.",
    "INVALID_ACTION": "Tighten action schema generation or add a pre-execution normalization rule.",
    "NAVIGATION": "Compare target selection and motion result across the failing public traces.",
    "PICK": "Verify hand state and target visibility, then use a bounded alternative pickup approach.",
    "PLACEMENT": "Use observed place_location or AABB evidence and verify the hand-state transition.",
    "PHYSICAL_POSTCONDITION": "Inspect the first expected state change and preserve UNKNOWN when evidence is absent.",
    "NPC_MISSING_FACT": "Extract the required fact and ask the highest-information allowed NPC.",
    "NPC_BAD_QUESTION": "Reject duplicate or irrelevant questions and follow recorded owner/redirect evidence.",
    "RAVEN_REASONING": "Inspect ranked candidate margins and crop compatibility on official screenshots.",
    "JIGSAW_GRID": "Inspect inferred grid cells and piece-to-cell assignments from public spatial evidence.",
    "JIGSAW_ROTATION": "Inspect bounded legal rotation evidence for the first rejected piece.",
    "JSON": "Constrain the model response to one action object and inspect the raw response.",
    "MODEL_API": "Compare retry, latency, and error rates before selecting a model.",
    "LOOP": "Change the recovery observation or subgoal after the first repeated signature.",
    "PREMATURE_FINISH": "Require task-specific completion evidence before terminal actions.",
    "TIME_BUDGET": "Stop low-value exploration and choose the highest-probability direct progress action.",
    "UNKNOWN": "Inspect the raw first-critical-error payload and extend the taxonomy.",
}
MAX_FAILURE_EXAMPLES = 3


def _read_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def analyze_failures(metrics_dir: Path) -> dict[str, Any]:
    official: dict[str, dict[str, Any]] = {}
    for path in sorted(metrics_dir.glob("episode_*.json")):
        episode = _read_object(path)
        if not episode:
            continue
        if episode.get("verified") is True and episode.get("termination_reason") == OFFICIAL_TERMINATION:
            official[str(episode.get("episode_id"))] = episode

    counts: Counter[str] = Counter()
    examples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(metrics_dir.glob("failure_*.json")):
        report = _read_object(path)
        if not report:
            continue
        episode_id = str(report.get("episode_id"))
        if episode_id not in official:
            continue
        failure = report.get("first_critical_error")
        if not isinstance(failure, dict):
            continue
        category = str(failure.get("category") or failure.get("error_type") or "UNKNOWN")
        counts[category] += 1
        if len(examples[category]) < MAX_FAILURE_EXAMPLES:
            examples[category].append(
                {
                    "episode_id": episode_id,
                    "task_type": report.get("task_type"),
                    "step": failure.get("step"),
                    "message": failure.get("message"),
                }
            )

    ranked = [
        {
            "rank": rank,
            "category": category,
            "count": count,
            "share": round(count / sum(counts.values()), 6),
            "recommended_next_fix": RECOMMENDATIONS.get(category, RECOMMENDATIONS["UNKNOWN"]),
            "examples": examples[category],
        }
        for rank, (category, count) in enumerate(counts.most_common(), start=1)
    ]
    return {
        "status": "VERIFIED_FAILURE_DATA" if ranked else "NOT_VERIFIED",
        "reason": None if ranked else "No official-service verified failed episodes were found.",
        "official_verified_episodes": len(official),
        "official_failures": sum(counts.values()),
        "ranked_failures": ranked,
    }


def write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Failure Analyzer",
        "",
        f"Status: **{payload['status']}**",
        "",
        "Only episodes evaluated by the official task service are included.",
        "",
    ]
    if payload["reason"]:
        lines.extend([f"REAL_ENV_NOT_AVAILABLE: {payload['reason']}", ""])
    lines.extend(
        [
            "| Rank | Category | Count | Share | Next fix |",
            "|---:|---|---:|---:|---|",
        ]
    )
    for row in payload["ranked_failures"]:
        lines.append(
            f"| {row['rank']} | {row['category']} | {row['count']} | {row['share']} | "
            f"{row['recommended_next_fix']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank failures from official-service verified episodes only.")
    parser.add_argument("--metrics-dir", type=Path, default=Path("logs/metrics"))
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark/failure_analysis"))
    args = parser.parse_args()
    payload = analyze_failures(args.metrics_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "failure_analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_markdown(args.output_dir / "failure_analysis.md", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
