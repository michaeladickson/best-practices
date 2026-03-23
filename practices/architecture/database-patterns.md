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

RLS adds implicit WHERE clauses to every query. No data is accessible via the public anon key until policies are created.

**Enable on every table:**
```sql
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
```

**Auto-enable on new tables** (event trigger — set once, never forget):
```sql
CREATE OR REPLACE FUNCTION rls_auto_enable()
RETURNS EVENT_TRIGGER LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog AS $$
DECLARE cmd record;
BEGIN
  FOR cmd IN SELECT * FROM pg_event_trigger_ddl_commands()
    WHERE command_tag IN ('CREATE TABLE', 'CREATE TABLE AS')
      AND schema_name = 'public'
  LOOP
    EXECUTE format('ALTER TABLE IF EXISTS %s ENABLE ROW LEVEL SECURITY', cmd.object_identity);
  END LOOP;
END; $$;

CREATE EVENT TRIGGER ensure_rls ON ddl_command_end
  WHEN TAG IN ('CREATE TABLE', 'CREATE TABLE AS')
  EXECUTE FUNCTION rls_auto_enable();
```

**Policy patterns — create separate policies per operation:**
```sql
-- SELECT: USING clause filters which rows are visible
CREATE POLICY "Users read own data"
  ON public.users FOR SELECT
  TO authenticated
  USING ( (SELECT auth.uid()) = id );

-- INSERT: WITH CHECK validates new row data
CREATE POLICY "Users create own profile"
  ON public.profiles FOR INSERT
  TO authenticated
  WITH CHECK ( (SELECT auth.uid()) = user_id );

-- UPDATE: USING (existing row) + WITH CHECK (new row)
CREATE POLICY "Users update own profile"
  ON public.profiles FOR UPDATE
  TO authenticated
  USING ( (SELECT auth.uid()) = user_id )
  WITH CHECK ( (SELECT auth.uid()) = user_id );

-- DELETE: USING clause determines deletable rows
CREATE POLICY "Users delete own data"
  ON public.food_logs FOR DELETE
  TO authenticated
  USING ( (SELECT auth.uid()) = user_id );
```

**Performance rules (critical — can be 99%+ improvement):**

1. **Wrap auth functions with SELECT** — prevents per-row evaluation:
   ```sql
   -- Bad: 179ms
   USING ( auth.uid() = user_id );
   -- Good: 9ms
   USING ( (SELECT auth.uid()) = user_id );
   ```

2. **Index columns used in policies:**
   ```sql
   CREATE INDEX idx_profiles_user_id ON profiles USING btree (user_id);
   -- 171ms → <0.1ms
   ```

3. **Always specify roles** (`TO authenticated` / `TO anon`) — avoids unnecessary evaluation for the wrong role.

4. **Filter client-side too** — duplicate policy logic in queries:
   ```typescript
   // Bad: full table scan then RLS filters
   supabase.from('food_logs').select()
   // Good: index scan + RLS confirms
   supabase.from('food_logs').select().eq('user_id', userId)
   ```

5. **Avoid joins in policies** — restructure to query from the user's perspective:
   ```sql
   -- Slow (9,000ms): joins to source table
   USING ( (SELECT auth.uid()) IN (
     SELECT user_id FROM team_user WHERE team_user.team_id = team_id
   ));
   -- Fast (20ms): no join
   USING ( team_id IN (
     SELECT team_id FROM team_user WHERE user_id = (SELECT auth.uid())
   ));
   ```

**Common mistakes:**
- UPDATE requires a corresponding SELECT policy to work
- `auth.uid()` returns NULL when unauthenticated — `NULL = user_id` silently fails. Guard: `auth.uid() IS NOT NULL AND auth.uid() = user_id`
- Never store authorization data in `raw_user_meta_data` (users can modify it) — use `raw_app_meta_data`
- JWTs aren't always fresh — role changes need JWT refresh before policies see them
- Security definer functions bypass RLS — never create in exposed schemas

**MFA enforcement:**
```sql
CREATE POLICY "Require MFA for updates"
  ON profiles AS RESTRICTIVE FOR UPDATE
  TO authenticated
  USING ((SELECT auth.jwt()->>'aal') = 'aal2');
```

**Service role bypasses RLS** — use server-side only, never expose to clients.

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
