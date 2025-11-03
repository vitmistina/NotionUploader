# Platform module

The `platform` package centralises cross-cutting infrastructure that the API
relies on. During the transition period existing modules re-export the new
interfaces, so imports such as `from src.settings import get_settings` continue
working. New code should import directly from `platform`.

## Entry points
- `platform.config` – Pydantic settings (`Settings`, `get_settings`).
- `platform.security` – API key dependencies (`api_key_header`, `verify_api_key`).
- `platform.clients` – infrastructure client factories (`RedisClient`, `get_redis`).

## Transition plan
Re-exports in `src/settings.py`, `src/security.py` and `src/services/redis.py`
will be removed after dependants update their imports. Prefer using the
`platform` package immediately to avoid breakage when the compatibility layer is
removed.
