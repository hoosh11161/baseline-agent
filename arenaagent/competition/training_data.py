from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OFFICIAL_TERMINATION = "evaluated_by_official_task_service"
SCHEMA_VERSION = "verified-action-trajectory-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_episode(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _label_action(episode: dict[str, Any], action: dict[str, Any]) -> str | None:
    if action.get("failed") is True:
        return "negative"
    if episode.get("success") is True:
        return "positive"
    return None


def export_verified_trajectories(
    metrics_dir: Path,
    output_path: Path,
    *,
    manifest_path: Path | None = None,
    include_unlabeled: bool = False,
) -> dict[str, Any]:
    """Export action examples only from official-service verified episodes.

    A successful episode supplies positive non-failed steps. Explicitly failed
    actions supply negative examples. Non-failed steps from a failed episode
    are excluded by default because final episode failure does not prove those
    individual actions were wrong.
    """
    samples: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    verified_episode_count = 0

    for path in sorted(metrics_dir.glob("episode_*.json")):
        episode = _load_episode(path)
        if episode is None:
            continue
        if episode.get("verified") is not True or episode.get("termination_reason") != OFFICIAL_TERMINATION:
            continue
        verified_episode_count += 1
        sources.append({"path": path.name, "sha256": _sha256(path)})
        actions = episode.get("world_state", {}).get("recent_actions", [])
        if not isinstance(actions, list):
            continue
        for action in actions:
            if not isinstance(action, dict):
                continue
            label = _label_action(episode, action)
            if label is None and not include_unlabeled:
                continue
            samples.append(
                {
                    "schema_version": SCHEMA_VERSION,
                    "episode_id": episode.get("episode_id"),
                    "task_type": episode.get("task_type"),
                    "episode_success": episode.get("success"),
                    "episode_score": episode.get("score"),
                    "label": label or "unlabeled",
                    "step": action.get("step"),
                    "state": action.get("state", {}),
                    "action": action.get("action", {}),
                    "result": action.get("result", {}),
                    "failure_class": action.get("failure_class", ""),
                    "run_metadata": episode.get("run_metadata", {}),
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(sample, ensure_ascii=False, sort_keys=True) + "\n" for sample in samples)
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary.write_text(body, encoding="utf-8")
    temporary.replace(output_path)

    label_counts = {
        "positive": sum(sample["label"] == "positive" for sample in samples),
        "negative": sum(sample["label"] == "negative" for sample in samples),
        "unlabeled": sum(sample["label"] == "unlabeled" for sample in samples),
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "VERIFIED_DATASET"
            if samples
            else "NO_LABELED_SAMPLES"
            if verified_episode_count
            else "NOT_VERIFIED"
        ),
        "verified_episodes": verified_episode_count,
        "sample_count": len(samples),
        "label_counts": label_counts,
        "output": output_path.name,
        "output_sha256": _sha256(output_path),
        "sources": sources,
        "policy": (
            "Only official-task-service verified episodes are accepted. "
            "Successful non-failed actions are positive; explicitly failed actions are negative."
        ),
    }
    manifest_target = manifest_path or output_path.with_suffix(output_path.suffix + ".manifest.json")
    manifest_target.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = manifest_target.with_suffix(manifest_target.suffix + ".tmp")
    temporary_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_manifest.replace(manifest_target)
    return manifest
