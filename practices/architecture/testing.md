# Testing Patterns

## FastAPI Testing

```python
from fastapi.testclient import TestClient

@pytest.fixture
def client(mock_db, admin_user_row):
    from src.api.main import app
    mock_db.set_result("FROM app_users WHERE id", [admin_user_row])
    return TestClient(app)

def test_get_sales(client, admin_token):
    response = client.get("/api/sales", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
```

## Mock DB Pattern

Create a fake connection that matches results by SQL fragment:

```python
class FakeConn:
    def set_result(self, sql_fragment: str, rows: list):
        """When a query contains this fragment, return these rows."""
        self._results[sql_fragment] = rows

@pytest.fixture
def mock_db():
    conn = FakeConn()
    # Patch get_connection() everywhere it's imported
    with patch("src.api.routes.sales.get_connection", return_value=conn):
        with patch("src.api.routes.inventory.get_connection", return_value=conn):
            yield conn
```

- `FakeRow`: dict subclass supporting both `row["key"]` and `row[0]` access
- `FakeCursor`: mimics psycopg2 with `fetchall()`, `fetchone()`, `rowcount`
- Patch `get_connection()` in every module that imports it

## Auth Fixtures

```python
@pytest.fixture
def admin_token():
    return create_access_token(user_id=1, role="admin", email="admin@test.com")

@pytest.fixture
def admin_user_row():
    return {
        "id": 1, "email": "admin@test.com", "role": "admin",
        "store_ids": ["store1"], "active": True,
        "password_hash": hash_password("correctpassword"),
    }
```

## Principles

- All tests mock the DB — no external services needed
- Set `JWT_SECRET` env var before importing app modules
- All tests run offline and deterministically
- Use `TestClient(app)` for endpoint testing

## Where Used

- **crumbl-ops**: Full test suite with FakeConn, FakeCursor, FakeRow pattern
