# Secrets Management

## Hierarchy

1. **Environment variables** (`.env` in dev, injected in prod)
2. **GCP Secret Manager** (production secrets, per-tenant tokens)
3. **Fernet encryption** (local token storage for CLI tools)

Never hardcode secrets. Never commit `.env` files.

## Environment Variables

```python
from dotenv import load_dotenv
load_dotenv()  # Load .env at module import time

# Access with fallbacks
api_key = os.environ.get("GEMINI_API_KEY", "")
```

Standard `.env` variables across projects:
- `GEMINI_API_KEY` — Gemini API key (prefer over Vertex AI)
- `GCP_PROJECT_ID` — GCP project for Vertex AI / Secret Manager fallback
- `SENDGRID_API_KEY` — Email delivery
- `API_KEY` — API authentication for local services

## GCP Secret Manager (Production)

```python
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = f"projects/{project}/secrets/{secret_name}/versions/latest"
value = client.access_secret_version(request={"name": name}).payload.data.decode("utf-8")
```

- Per-tenant secrets: `qbo-lexington`, `qbo-richmond` (one per store)
- Cloud Run: reference via `--set-secrets=VAR=secret-id:latest`
- SA key fallback paths: `~/project-sa-key.json`, `./project-sa-key.json`

## Token Encryption (Local Storage)

```python
from cryptography.fernet import Fernet

# Generate key once: Fernet.generate_key().decode()
# Store in TOKEN_ENCRYPTION_KEY env var

f = Fernet(os.environ["TOKEN_ENCRYPTION_KEY"].encode())
encrypted = f.encrypt(plaintext.encode()).decode()
decrypted = f.decrypt(ciphertext.encode()).decode()
```

- Set file permissions: `chmod(0o600)` on encrypted token files
- Migration pattern: try encrypted first, fall back to plaintext, re-save encrypted

## FastAPI Authentication

```python
from fastapi.security import APIKeyHeader
from fastapi import Security, HTTPException

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def _require_api_key(key: str = Security(_api_key_header)):
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API_KEY not configured")
    if not key or key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
```

For full user auth: JWT (HS256, 24h expiry) with bcrypt password hashing.

## Rate Limiting

```python
# In-memory rate limiter on login endpoint
# 5 attempts per 15-min window, per-IP
# Hard cap on tracked IPs (10k) to prevent memory exhaustion
```

## Pydantic SecretStr

```python
from pydantic import SecretStr

class Settings(BaseSettings):
    qbo_client_secret: SecretStr = SecretStr("")
```

Prevents accidental logging of secrets in repr/str output.

## Mobile App Keys

- Supabase URL + anon key: safe to embed in app (RLS protects data)
- GEMINI_API_KEY: keep server-side only (Edge Functions)
- Third-party credentials (Eight Sleep, etc.): store as Supabase secrets

## Where Used

- **crumbl-ops**: GCP Secret Manager, JWT auth, rate limiting, SecretStr
- **wealth-mgmt**: Fernet encryption for Plaid tokens, API key header
- **healthpulse**: Supabase RLS, Edge Function secrets, encrypted AsyncStorage
