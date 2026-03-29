# SQL Injection Prevention

Parameterized queries are the primary defense against SQL injection. All queries that include external or user-supplied input must use parameter placeholders, never f-strings or string concatenation.

## Correct Pattern (psycopg2)

Use `%s` placeholders and pass values as a tuple:

```python
# Single parameter
conn.execute("SELECT * FROM t WHERE id = %s", (user_id,))

# Multiple parameters
conn.execute(
    "SELECT * FROM orders WHERE store_id = %s AND date = %s",
    (store_id, order_date),
)

# INSERT
conn.execute(
    "INSERT INTO employees (name, position, rate) VALUES (%s, %s, %s)",
    (name, position, rate),
)
```

## Anti-Pattern

Never interpolate external input into SQL strings:

```python
# DANGEROUS — SQL injection vector
conn.execute(f"SELECT * FROM t WHERE id = '{user_id}'")

# ALSO DANGEROUS — string concatenation
conn.execute("SELECT * FROM t WHERE id = '" + user_id + "'")
```

An attacker supplying `'; DROP TABLE employees; --` as `user_id` executes arbitrary SQL.

## ILIKE and Wildcards

When using `%s` parameters with `LIKE`/`ILIKE`, the `%` wildcard must be escaped as `%%` in the query string, or built into the parameter value:

```python
# Option 1: Build the wildcard into the parameter value (preferred)
search_term = f"%{query}%"
conn.execute(
    "SELECT * FROM customers WHERE name ILIKE %s",
    (search_term,),
)

# Option 2: Use %% in the query string for literal %
conn.execute(
    "SELECT * FROM customers WHERE name ILIKE '%%' || %s || '%%'",
    (query,),
)
```

## When F-Strings Are Acceptable

F-string SQL is acceptable when the interpolated values are **hardcoded internal values** — column names, table names from config, sort directions — never user or external input:

```python
# OK — column name is a hardcoded constant, not user input
sort_col = "created_at"
direction = "DESC"
conn.execute(
    f"SELECT * FROM orders WHERE store_id = %s ORDER BY {sort_col} {direction}",
    (store_id,),
)

# OK — table name from internal config
table = "revenue_daily"
conn.execute(f"SELECT sum(amount) FROM {table} WHERE date = %s", (date,))
```

The key distinction: if the value could ever originate from a user request, URL parameter, form field, or external API, it must be parameterized.

## Where Used

- **crumbl-ops**: `src/ops/` (database queries), `src/api/routes/` (API endpoints accepting user input)
