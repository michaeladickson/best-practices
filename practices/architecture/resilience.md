# Resilience Patterns

## Circuit Breaker

Prevent cascading failures when an external service is down.

```python
class CircuitBreaker:
    def __init__(self, name, failure_threshold=3, recovery_timeout=300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.state = "CLOSED"  # CLOSED → OPEN → HALF_OPEN
        self.last_failure_time = None

    def allow_request(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        return True  # HALF_OPEN: allow probe

    def record_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            self.last_failure_time = time.time()
```

Use one breaker per external API (QBO, Plaid, Gemini, etc.).

## Run Governor

Prevent runaway pipelines (infinite loops, timeout hangs).

```python
class RunGovernor:
    def __init__(self, max_steps=50, max_duration_seconds=600):
        self.max_steps = max_steps
        self.max_duration = max_duration_seconds

    def start(self):
        self.start_time = time.time()
        self.steps = 0

    def step(self, label: str):
        self.steps += 1
        elapsed = time.time() - self.start_time
        if self.steps > self.max_steps:
            raise GovernorLimitError(f"Exceeded {self.max_steps} steps")
        if elapsed > self.max_duration:
            raise GovernorLimitError(f"Exceeded {self.max_duration}s")
```

Use for nightly sync jobs, batch processing pipelines.

## Retry with Exponential Backoff

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def call_external_api():
    ...
```

Standard: 3 attempts, 2s/4s/8s backoff (capped at 10s).

## OAuth Token Refresh

- Access tokens expire hourly — auto-refresh on `AuthorizationException`
- Refresh tokens are single-use — save new token immediately after refresh
- Use a threading lock to prevent concurrent token fetches
- If Secret Manager unavailable, warn and continue with stale token

## Async Error Gathering

```python
tasks = [sync_store(store, date) for store in stores]
results = await asyncio.gather(*tasks, return_exceptions=True)
for store, result in zip(stores, results):
    if isinstance(result, Exception):
        log.error("sync_failed", store=store.id, error=str(result))
```

Always use `return_exceptions=True` so one failure doesn't cancel others.

## Where Used

- **crumbl-ops**: Circuit breaker + governor in `src/resilience.py`, tenacity on QBO calls
