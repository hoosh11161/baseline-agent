#!/usr/bin/env python
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

PROTO_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "protocol"))
PROTO_INCLUDE_ARENA = os.path.join(PROTO_DIR, "arena")
PROTO_INCLUDE_TONGTONG = os.path.join(PROTO_DIR, "tongtong")
ARENA_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "arenaagent", "generated"))
OUTPUT_DIR = os.path.abspath(
    os.path.join(
        SCRIPT_DIR, "..", "arenaagent", "generated"
    )
)

BLACKLIST_DIRS = [""]


def is_blacklisted(path: str) -> bool:
    relative = os.path.relpath(path, PROTO_DIR)
    return any(relative.split(os.sep)[0] == b for b in BLACKLIST_DIRS)


def _is_under_output(path: str) -> bool:
    try:
        return os.path.commonpath([OUTPUT_DIR, path]) == OUTPUT_DIR
    except ValueError:
        return False


def _is_under(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def ensure_arena_package() -> None:
    os.makedirs(ARENA_DIR, exist_ok=True)
    init_path = os.path.join(ARENA_DIR, "__init__.py")
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("# Auto-generated\n")


def find_proto_files():
    for root, _, files in os.walk(PROTO_DIR):
        if is_blacklisted(root):
            continue
        for f in files:
            if f.endswith(".proto"):
                yield os.path.join(root, f)


def ensure_init_packages(relevant_path: str):
    """Ensure all intermediate folders have __init__.py"""
    pkg_dir = os.path.dirname(relevant_path)
    while pkg_dir and _is_under_output(pkg_dir):
        init_path = os.path.join(pkg_dir, "__init__.py")
        if not os.path.exists(init_path):
            with open(init_path, "w") as f:
                f.write("# Auto-generated\n")
        parent = os.path.dirname(pkg_dir)
        if parent == pkg_dir:
            break
        pkg_dir = parent


def generate_pb(proto_file: str):
    proto_root = PROTO_INCLUDE_TONGTONG if _is_under(proto_file, PROTO_INCLUDE_TONGTONG) else PROTO_DIR
    relative_path = os.path.relpath(proto_file, proto_root)
    output_subdir = os.path.join(OUTPUT_DIR, os.path.dirname(relative_path))
    os.makedirs(output_subdir, exist_ok=True)

    include_paths = [proto_root, PROTO_DIR, PROTO_INCLUDE_ARENA, PROTO_INCLUDE_TONGTONG]
    include_paths = [p for p in dict.fromkeys(include_paths) if os.path.exists(p)]

    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        *[f"-I{path}" for path in include_paths],
        f"--python_out={OUTPUT_DIR}",
        f"--pyi_out={OUTPUT_DIR}",
        f"--grpc_python_out={OUTPUT_DIR}",
        proto_file,
    ]
    print(f"[Info]  Compiling {proto_file}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Generate __init__.py for all relevant directories
    base = os.path.splitext(os.path.relpath(proto_file, proto_root))[0]
    relevant_path = os.path.join(OUTPUT_DIR, base)
    ensure_init_packages(relevant_path)

def main():
    if not os.path.exists(PROTO_DIR):
        print(f"[Error] Proto directory not found: {PROTO_DIR}")
        sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ensure_arena_package()

    proto_files = list(find_proto_files())
    if not proto_files:
        print("[Warning]  No .proto files found.")
        return

    for proto_file in proto_files:
        generate_pb(proto_file)

    print("[Info] gRPC Python code generation complete.")


if __name__ == "__main__":
    main()
