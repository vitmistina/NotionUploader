# Changelog

## Unreleased
- Removed backward-compatibility shims (`src/metrics.py`, `src/nutrition.py`, `src/settings.py`, `src/security.py`, `src/services/redis.py`) now that all imports resolve through `src.platform` and the domain packages.
- Dropped the runtime monkeypatch that aliased the standard-library `platform` module to `src.platform`; code should import `src.platform` explicitly.
