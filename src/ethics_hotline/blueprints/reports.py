"""Reports blueprint.

Registered empty. Routes are added in a later pass.
"""

from __future__ import annotations

from flask import Blueprint

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")
