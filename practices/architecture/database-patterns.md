# Database Patterns

## PostgreSQL (Production)

### Connection Pool
```python
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(minconn=2, maxconn=15)
```
- Health check on `get_connection()`: execute `SELECT 1` to detect stale connections after scale-to-zero idle
- Auto-commit on context manager exit (no exception) / auto-rollback on exception
- `reset_pool()` available for late `load_dotenv()` scenarios

### Idempotent Upserts
```sql
INSERT INTO table (key, value) VALUES (?, ?)
ON CONFLICT(key) DO UPDATE SET value = excluded.value
```
Always use `ON CONFLICT` for operations that may be retried or re-run.

### Row-Level Security (Supabase)
```sql
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can read own data"
  ON public.users FOR SELECT
  USING (auth.uid() = id);
```
Enable RLS on every table. Create policies for SELECT, INSERT, UPDATE, DELETE separately.

### Indexing Strategy
```sql
-- Composite indexes for common user+date queries
CREATE INDEX idx_food_logs_user_date ON food_logs (user_id, logged_at DESC);

-- Conditional unique for deduplication of external data
CREATE UNIQUE INDEX idx_workouts_healthkit_uuid
  ON workouts (user_id, healthkit_uuid)
  WHERE healthkit_uuid IS NOT NULL;
```

## SQLite (Local / CLI Tools)

### Setup
```python
conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row      # Access columns by name
conn.execute("PRAGMA journal_mode=WAL")  # Concurrent reads
conn.execute("PRAGMA foreign_keys=ON")
```

### Full-Text Search (FTS5)
```sql
CREATE VIRTUAL TABLE posts_fts USING fts5(
    title, content_preview, key_takeaway,
    content='posts', content_rowid='id'
);
-- Keep in sync with triggers
CREATE TRIGGER posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, title, content_preview, key_takeaway)
    VALUES (new.id, new.title, new.content_preview, new.key_takeaway);
END;
```

## General Rules

- Use `Decimal` for financial fields, never `float`
- Always store timestamps as UTC (`timestamptz` in Postgres, ISO strings in SQLite)
- Include `source` field to track data origin (manual, API, healthkit, etc.)
- Include external UUIDs (healthkit_uuid, plaid_id) for deduplication

## Where Used

- **crumbl-ops**: PostgreSQL via Cloud SQL, ThreadedConnectionPool
- **wealth-mgmt**: SQLite with FTS5 for digest search, Supabase for remote
- **healthpulse**: Supabase PostgreSQL with RLS, JSONB for flexible structures
