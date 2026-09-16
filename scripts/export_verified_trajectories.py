from __future__ import annotations

import argparse
import json
from pathlib import Path

from arenaagent.competition.training_data import export_verified_trajectories


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export auditable action-training JSONL from official verified episode metrics."
    )
    parser.add_argument("--metrics-dir", type=Path, default=Path("logs/metrics"))
    parser.add_argument("--output", type=Path, default=Path("training/verified_actions.jsonl"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--include-unlabeled", action="store_true")
    args = parser.parse_args()
    manifest = export_verified_trajectories(
        args.metrics_dir,
        args.output,
        manifest_path=args.manifest,
        include_unlabeled=args.include_unlabeled,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
