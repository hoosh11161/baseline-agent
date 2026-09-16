from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(slots=True)
class Check:
    name: str
    status: str
    detail: str


def check_python() -> Check:
    ok = sys.version_info >= (3, 12)
    return Check("python", "PASS" if ok else "FAIL", sys.version.split()[0])


def check_import(module_name: str) -> Check:
    try:
        importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - preflight must report every import failure
        return Check(f"import:{module_name}", "FAIL", f"{type(exc).__name__}: {exc}")
    return Check(f"import:{module_name}", "PASS", "importable")


def check_asset(relative_path: str, minimum_size: int) -> Check:
    path = REPO_ROOT / relative_path
    if not path.is_file():
        return Check(f"asset:{relative_path}", "FAIL", "missing")
    size = path.stat().st_size
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    status = "PASS" if size >= minimum_size else "FAIL"
    return Check(f"asset:{relative_path}", status, f"bytes={size}, sha256_prefix={digest}")


def check_port(name: str, host: str, port: int) -> Check:
    try:
        with socket.create_connection((host, port), timeout=0.75):
            return Check(f"service:{name}", "PASS", f"reachable at {host}:{port}")
    except OSError as exc:
        return Check(f"service:{name}", "BLOCKED", f"not reachable at {host}:{port}: {exc}")


def check_model_credentials() -> Check:
    names = (
        "VLM_CLIENT_CFG_API_KEY",
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "DASHSCOPE_API_KEY",
        "ZHIPU_API_KEY",
        "ARK_API_KEY",
    )
    configured = [name for name in names if os.getenv(name)]
    if configured:
        return Check("model_credentials", "PASS", "configured variables: " + ", ".join(configured))
    return Check("model_credentials", "BLOCKED", "no supported API-key environment variable is set")


def check_release_dir(release_dir: Path | None) -> Check:
    if release_dir is None:
        return Check("official_release", "BLOCKED", "no --release-dir supplied")
    if not release_dir.is_dir():
        return Check("official_release", "FAIL", f"directory not found: {release_dir}")
    expected = (
        "arena_offline/arena_offline.exe",
        "start_test.bat",
    )
    found = [item for item in expected if (release_dir / item).exists()]
    status = "PASS" if len(found) == len(expected) else "BLOCKED"
    return Check("official_release", status, f"found {len(found)}/{len(expected)} required launch/package files")


def run_checks(release_dir: Path | None = None) -> dict[str, Any]:
    checks = [
        check_python(),
        check_import("arenaagent.builder"),
        check_import("arenaagent.generated.arena.agent.arena_agent_service_pb2_grpc"),
        check_import("arenaagent.generated.tongsim.tongsim_service_pb2_grpc"),
        check_asset("arenaagent/vlm_agent/skills/Resnet18_MLP_epoch_199.pth", 50_000_000),
        check_asset("arenaagent/vlm_agent/skills/embedding.npy", 50_000),
        check_asset("arenaagent/vlm_agent/skills/group_coords.json", 5_000),
        check_model_credentials(),
        check_port("task_service", "127.0.0.1", 50051),
        check_port("tongsim_proxy", "127.0.0.1", 50060),
        check_release_dir(release_dir),
    ]
    hard_failures = [check for check in checks if check.status == "FAIL"]
    blockers = [check for check in checks if check.status == "BLOCKED"]
    return {
        "status": "FAIL" if hard_failures else "BLOCKED" if blockers else "PASS",
        "ready_for_official_benchmark": not hard_failures and not blockers,
        "checks": [asdict(check) for check in checks],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only competition environment preflight.")
    parser.add_argument("--release-dir", type=Path)
    parser.add_argument("--output", type=Path, default=Path("benchmark/preflight.json"))
    args = parser.parse_args()
    payload = run_checks(args.release_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(1 if payload["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
