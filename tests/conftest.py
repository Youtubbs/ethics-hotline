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

import dataclasses
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

import ethics_hotline.blueprints.reports as reports_blueprint
from ethics_hotline.app import create_app
from ethics_hotline.aws.comprehend import ComprehendClient
from ethics_hotline.aws.s3 import S3Client
from ethics_hotline.aws.textract import TextractClient
from ethics_hotline.models import db as _db

# A bucket name that does not exist anywhere
TEST_BUCKET = "test-evidence-bucket"


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
    transaction means temporarily replacing the registered engine itself with a connection
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


class NoNetworkSession:
    """ Stands in for a boto3 session and refuses to build a real client. """

    def client(self, service_name: str):  # noqa: ANN201 - never returns
        raise AssertionError(
            f"A test tried to build a real {service_name} client. "
            "The suite must never reach a live AWS endpoint."
        )


@pytest.fixture()
def fake_comprehend() -> MagicMock:
    """A Comprehend wrapper double that finds no PII and no key phrases."""
    fake = MagicMock(spec=ComprehendClient)
    fake.detect_pii_entities.return_value = []
    fake.detect_key_phrases.return_value = []
    return fake


@pytest.fixture()
def fake_textract() -> MagicMock:
    """A Textract wrapper double that extracts nothing by default."""
    fake = MagicMock(spec=TextractClient)
    fake.detect_document_text.return_value = []
    return fake


@pytest.fixture()
def fake_s3() -> MagicMock:
    """An S3 wrapper double that stores nothing and hands back a fixed key."""
    fake = MagicMock(spec=S3Client)
    fake.put_object.return_value = "evidence/00000000000000000000000000000000.png"
    fake.get_object.return_value = b"fake-evidence-bytes"
    return fake


@pytest.fixture(autouse=True)
def injected_aws(
    monkeypatch: pytest.MonkeyPatch,
    fake_comprehend: MagicMock,
    fake_textract: MagicMock,
    fake_s3: MagicMock,
) -> dict[str, MagicMock]:
    """Inject the fake wrappers at the point the route constructs them."""
    monkeypatch.setattr(reports_blueprint, "get_session", NoNetworkSession)
    monkeypatch.setattr(
        reports_blueprint, "ComprehendClient", lambda session: fake_comprehend
    )
    monkeypatch.setattr(
        reports_blueprint, "TextractClient", lambda session: fake_textract
    )
    monkeypatch.setattr(
        reports_blueprint, "S3Client", lambda session, bucket: fake_s3
    )
    monkeypatch.setattr(
        reports_blueprint,
        "settings",
        dataclasses.replace(reports_blueprint.settings, aws_s3_bucket=TEST_BUCKET),
    )
    return {"comprehend": fake_comprehend, "textract": fake_textract, "s3": fake_s3}


@pytest.fixture()
def client(app: Flask, db_session: None) -> FlaskClient:
    """A test client whose requests share the rollback-per-test session."""
    return app.test_client()
