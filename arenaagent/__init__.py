import importlib
import sys

# Import generated protobuf modules and set them in sys.modules for easier access
try:
    _generated_arena_message = importlib.import_module(
        "arenaagent.generated.arena.message"
    )
    _generated_arena_agent = importlib.import_module(
        "arenaagent.generated.arena.agent"
    )
    _generated_launcher = importlib.import_module(
        "arenaagent.generated.launcher.proto"
    )
    sys.modules.setdefault("arena.message", _generated_arena_message)
    sys.modules.setdefault("arena.agent", _generated_arena_agent)
    sys.modules.setdefault("launcher.proto", _generated_launcher)
except Exception:
    pass
