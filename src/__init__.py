"""Source package for NotionUploader."""

from __future__ import annotations

import importlib
import sys

_platform_module = importlib.import_module("src.platform")
sys.modules["platform"] = _platform_module
sys.modules["platform.config"] = importlib.import_module("src.platform.config")
sys.modules["platform.security"] = importlib.import_module("src.platform.security")
sys.modules["platform.clients"] = importlib.import_module("src.platform.clients")
