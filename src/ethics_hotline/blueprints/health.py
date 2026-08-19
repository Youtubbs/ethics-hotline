"""Liveness and readiness endpoints.

Liveness only confirms the process is up. Readiness confirms the database
is reachable; it never touches Comprehend or Textract.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ethics_hotline.models import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/live")
def live() -> tuple[Response, int]:
    """Report that the process is running, with no dependency checks."""
    return jsonify({"status": "ok"}), 200


@health_bp.get("/ready")
def ready() -> tuple[Response, int]:
    """Report readiness by running SELECT 1 against the database."""
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return jsonify({"status": "unavailable"}), 503
    return jsonify({"status": "ok"}), 200
