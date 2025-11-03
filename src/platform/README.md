# Platform module

The `platform` package centralises cross-cutting infrastructure that the API
relies on. Import from this package directly to access configuration, security
dependencies, and infrastructure clients.

## Entry points
- `platform.config` – Pydantic settings (`Settings`, `get_settings`).
- `platform.security` – API key dependencies (`api_key_header`, `verify_api_key`).
- `platform.clients` – infrastructure client factories (`RedisClient`, `get_redis`).

## Transition plan
Compatibility shims under `src/settings.py`, `src/security.py`, and
`src/services/redis.py` have been removed. Update any remaining out-of-tree
scripts to import from `src.platform` directly.
