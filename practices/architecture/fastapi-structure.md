# FastAPI Project Structure

## Pattern

Organize FastAPI apps with modular routers per domain, a service layer for orchestration, and a data layer for DB access.

## Structure

```
src/
  api/
    main.py              # App factory, CORS, router registration, SPA fallback
    auth.py              # JWT auth, rate limiting, Depends(get_current_user)
    routes/
      {domain}.py        # One router per domain (sales, inventory, etc.)
  {domain}/
    models.py            # Pydantic models for this domain
    service.py           # Business logic / orchestration
  ops/
    db.py                # Connection pool, context manager
    schema.sql           # Core tables
    migrations/          # Versioned .sql files (001.sql, 002.sql, ...)
  config.py              # Settings loading, cached config helpers
```

## Router Registration

```python
# main.py
app.include_router(cookies.router, prefix="/api/cookies", tags=["cookies"])
app.include_router(sales.router, prefix="/api/sales", tags=["sales"])
# ... one line per domain
```

## Key Conventions

- Register CORS middleware early with configurable origins via `CORS_ORIGINS` env var
- Warm DB pool in `app.on_event("startup")` with a background thread (non-blocking first request)
- Serve React SPA as a catch-all route after all `/api` routes
- Mount static assets separately at `/assets`
- Expose `/api/health` for load balancer checks

## Database Migrations

- Versioned SQL files in `migrations/` (001.sql, 002.sql, ...)
- Tracked in `schema_migrations` table (name, applied_at)
- Auto-apply on startup via `_apply_migrations()` in main.py
- Sorted lexicographically, applied once per instance

## Where Used

- **crumbl-ops**: Full implementation with 19 domain routers
- **wealth-mgmt**: Lighter version with Plaid + manual asset endpoints
