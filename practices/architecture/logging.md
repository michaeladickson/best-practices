# Logging with Structlog

## Setup

Use structlog everywhere. Never use `import logging` directly.

```python
import structlog
log = structlog.get_logger()
```

## Patterns

```python
# Success
log.info("digest_sent", status_code=response.status_code, recipient=to_email)

# Warning (degraded but continuing)
log.warning("feed_fetch_failed", source=feed_name, error=str(e))

# Error (with traceback)
log.error("json_parse_failed", error=str(e), response=text[:200], exc_info=True)
```

## Conventions

- Use snake_case event names: `digest_sent`, `sync_failed`, `token_refreshed`
- Include key-value context as kwargs, not in the message string
- Use `exc_info=True` on errors for full tracebacks
- Truncate large values in log context (e.g., `response=text[:200]`)

## Module Prefixes (TypeScript/Mobile)

For React Native console logging:
```typescript
console.error('[Sync] Workout sync error:', e);
console.log('[HealthKit] Steps fetched:', count);
```

Use `[Module]` prefixes for filtering in device logs.

## Where Used

- All Python projects use structlog
- healthpulse uses console.log with `[Module]` prefixes
