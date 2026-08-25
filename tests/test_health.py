"""Tests for the liveness and readiness endpoints."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient
from sqlalchemy.exc import OperationalError

from ethics_hotline.models import db


def test_live_returns_200_with_no_dependency_check(client: FlaskClient) -> None:
    response = client.get("/live")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_returns_200_when_database_is_reachable(client: FlaskClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_ready_returns_503_when_database_is_unreachable(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*args: object, **kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(db.session, "execute", _boom)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.get_json() == {"status": "unavailable"}
