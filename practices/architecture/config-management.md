# Configuration Management

## Environment-Driven Config

```
.env (dev, gitignored) → env vars (prod, injected by Cloud Run / Supabase)
```

Use `python-dotenv` and load early:
```python
from dotenv import load_dotenv
load_dotenv()
```

## YAML for Structured Config

Use YAML for lists/hierarchies that change independently of code:
- RSS feed sources (`feeds.yaml`)
- Project context for AI (`context.yaml`)
- Store/location metadata

```python
with open(path) as f:
    config = yaml.safe_load(f)
```

## CSV for User-Editable Data

Use CSV when non-developers need to maintain the data:
- Manual asset values
- Holdings/portfolios
- Reference data

```python
import csv
with open(path) as f:
    rows = list(csv.DictReader(f))
```

Benefit: editable in Excel, version-controllable in git.

## Database for Runtime Config

For config that changes at runtime (store settings, feature flags):
- Store in DB, not files
- Cache with TTL (5 min)
- Thread-safe with double-checked locking

```python
_cache = {}
_cache_ts = 0.0
CACHE_TTL = 300  # 5 minutes

def get_stores():
    if time.time() - _cache_ts < CACHE_TTL and _cache:
        return _cache
    # fetch from DB, update cache
```

## Feature Flags

Use CLI flags for pipeline control, not runtime feature flags:
```python
@click.option("--skip-qbo", is_flag=True)
@click.option("--skip-inventory", is_flag=True)
```

## Where Used

- **crumbl-ops**: DB config with TTL cache, CLI flags for pipeline
- **wealth-mgmt**: YAML feeds, CSV manual data, env vars for secrets
- **healthpulse**: Constants module for app-wide values, Supabase env for secrets
