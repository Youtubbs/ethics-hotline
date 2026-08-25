"""Shared pytest fixtures: the app, a test client, and a per-test rollback.

Normally, requires a real Postgres reachable at DATABASE_URL with the schema already
built via 'flask db upgrade'. Defaults to the same local Postgres described 
in .env.example so the suite works unmodified whether it runs on the host or
inside the api container, where DATABASE_URL is already set by docker-compose.yml.

Added tests to docker-compose.yml, so you can just run 'docker compose run --rm tests'
instead of worrying about db being up and such
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from dotenv import load_dotenv

# Load .env first so a real DATABASE_URL there is picked up before the
# fallback below is considered; load_dotenv() never overrides a variable
# that is already set, so an exported shell value still wins over both.
load_dotenv()

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/ethics_hotline"
)
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest
from flask import Flask
from flask.testing import FlaskClient

from ethics_hotline.app import create_app
from ethics_hotline.models import db as _db


@pytest.fixture(scope="session")
def app() -> Flask:
    """Build the Flask app once for the whole test session."""
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def db_session(app: Flask) -> Iterator[None]:
    """Roll back every database change a test makes, including committed ones.

    Flask-SQLAlchemy's Session.get_bind() always prefers the app's
    registered engine over a session-level bind, so joining an external
    transaction (the standard SQLAlchemy rollback-per-test recipe) means
    temporarily replacing the registered engine itself with a connection
    that already has a transaction open, not just constructing a Session
    with bind=connection. join_transaction_mode="create_savepoint" then
    makes each commit the app code issues open a new SAVEPOINT instead of
    ending that outer transaction, so the final rollback here undoes
    everything regardless of how many times a route committed.
    """
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        real_engine = _db.engines[None]
        _db.engines[None] = connection

        old_session = _db.session
        _db.session = _db._make_scoped_session(
            options={"bind": connection, "join_transaction_mode": "create_savepoint"}
        )

        yield

        _db.session.remove()
        transaction.rollback()
        connection.close()
        _db.session = old_session
        _db.engines[None] = real_engine


@pytest.fixture()
def client(app: Flask, db_session: None) -> FlaskClient:
    """A test client whose requests share the rollback-per-test session."""
    return app.test_client()
