# Platform module

The `platform` package centralises cross-cutting infrastructure that the API
relies on. Compatibility shims such as `src.settings` have been removed, so
import directly from `platform.*` modules.

## Entry points
- `platform.config` – Pydantic settings (`Settings`, `get_settings`).
- `platform.security` – API key dependencies (`api_key_header`, `verify_api_key`).
- `platform.clients` – infrastructure client factories (`RedisClient`, `get_redis`).

## Transition plan
Legacy re-export modules were removed in favour of `platform` imports. Update
any remaining downstream consumers to point at this package.
