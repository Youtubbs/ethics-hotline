"""Organizations blueprint.

Registered empty. Routes are added in a later pass.
"""

from __future__ import annotations

from flask import Blueprint

organizations_bp = Blueprint("organizations", __name__, url_prefix="/organizations")
