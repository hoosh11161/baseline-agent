from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from arenaagent.competition.replay import replay_public_trace


def _read_trace(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("trace must be a JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay public observations/actions through local guards.")
    parser.add_argument("trace", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark/replay/replay_result.json"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs/replay"))
    args = parser.parse_args()
    result = replay_public_trace(_read_trace(args.trace), log_dir=args.log_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
