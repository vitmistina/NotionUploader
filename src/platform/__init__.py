from __future__ import annotations

import importlib
import importlib.util
import sys
import sysconfig
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "_stdlib_platform", Path(sysconfig.get_path("stdlib")) / "platform.py"
)
_stdlib_platform = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader  # for type checkers
_spec.loader.exec_module(_stdlib_platform)

for name in dir(_stdlib_platform):
    if not name.startswith("_") and name not in globals():
        globals()[name] = getattr(_stdlib_platform, name)

from .config import Settings, get_settings  # noqa: E402,F401
from .security import api_key_header, verify_api_key  # noqa: E402,F401
from .clients import RedisClient, get_redis  # noqa: E402,F401

config = importlib.import_module("src.platform.config")
security = importlib.import_module("src.platform.security")
clients = importlib.import_module("src.platform.clients")

sys.modules.setdefault("src.platform.config", config)
sys.modules.setdefault("src.platform.security", security)
sys.modules.setdefault("src.platform.clients", clients)

__all__ = list(
    dict.fromkeys(
        list(getattr(_stdlib_platform, "__all__", []))
        + [
            "Settings",
            "get_settings",
            "api_key_header",
            "verify_api_key",
            "RedisClient",
            "get_redis",
        ]
    )
)
