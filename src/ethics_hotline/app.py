"""Flask application factory.

Builds and configures the app: database binding, structured logging,
request-logging middleware, the global error handler, and blueprints.
Routes live entirely in blueprints, never on the app object.
"""

from __future__ import annotations

from flask import Flask
from flask_migrate import Migrate

from ethics_hotline.blueprints.health import health_bp
from ethics_hotline.blueprints.organizations import organizations_bp
from ethics_hotline.blueprints.reports import reports_bp
from ethics_hotline.config import settings
from ethics_hotline.errors import register_error_handlers
from ethics_hotline.logging import configure_logging
from ethics_hotline.middleware import register_request_logging
from ethics_hotline.models import db

migrate = Migrate()


def create_app() -> Flask:
    """Build and return a configured Flask application."""
    configure_logging()

    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.database_url

    db.init_app(app)
    migrate.init_app(app, db)

    register_error_handlers(app)
    register_request_logging(app)

    app.register_blueprint(health_bp)
    app.register_blueprint(organizations_bp)
    app.register_blueprint(reports_bp)

    return app
