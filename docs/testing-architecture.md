# Test container and rollback-per-test

```mermaid
flowchart LR
    dev["docker compose run --rm tests"]
    build["Dockerfile: test stage\npyproject + tests/ + migrations/"]
    db[("db service\npostgres:16-alpine")]
    upgrade["run_tests.py\nflask db upgrade"]
    pytest["run_tests.py\npytest -q"]

    dev --> build
    build -->|waits for healthy| db
    build --> upgrade
    upgrade -->|applies migrations| db
    upgrade --> pytest
    pytest -->|37 tests, real Postgres| db

    classDef implemented fill:#3b6fb6,stroke:#1f3f6e,color:#ffffff
    class dev,build,db,upgrade,pytest implemented
```

```mermaid
flowchart TD
    routecall["route code calls db.session.execute(...)"]
    getbind["Session.get_bind()"]
    check2{"None in\nself._db.engines?"}
    engine["returns the pooled Engine\n(a fresh connection each time)"]
    fallback["falls back to self.bind\n(our test connection)"]

    routecall --> getbind --> check2
    check2 -->|yes, almost always| engine
    check2 -->|no| fallback

    classDef bad fill:#c0392b,stroke:#6e1f16,color:#ffffff
    classDef good fill:#3b6fb6,stroke:#1f3f6e,color:#ffffff
    class engine bad
    class fallback good
```

```python
connection = _db.engine.connect()
transaction = connection.begin()

real_engine = _db.engines[None]
_db.engines[None] = connection          # get_bind() now hands out our connection

old_session = _db.session
_db.session = _db._make_scoped_session(
    options={"bind": connection, "join_transaction_mode": "create_savepoint"}
)

yield  # the test runs here

_db.session.remove()
transaction.rollback()                  # undoes everything, no matter how many commits happened
connection.close()
_db.session = old_session
_db.engines[None] = real_engine
```
