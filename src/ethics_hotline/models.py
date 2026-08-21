"""SQLAlchemy 2.0 ORM models for organizations and reports.

Uses the typed declarative style ('Mapped' / 'mapped_column') on top of
Flask-SQLAlchemy's 'db.Model', so the same 'db' instance can be handed to
the app factory and to Flask-Migrate. No engine, session
lifecycle, or migration is configured here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()


class Organization(db.Model):
    """A compliance customer whose employees can submit anonymous reports."""

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    industry: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    reports: Mapped[list["Report"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Report(db.Model):
    """An anonymous report submitted against an organization.

    'text' and 'evidence_text' hold only the redacted content once PII
    screening has run. 'version' supports optimistic-locking concurrency
    control.
    """

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id"), nullable=False
    )
    text: Mapped[str] = mapped_column(nullable=False)
    contained_pii: Mapped[bool] = mapped_column(nullable=False, default=False)
    category: Mapped[Optional[str]] = mapped_column(nullable=True)
    suggested_category: Mapped[Optional[str]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(nullable=False, default="new")
    submitted_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    evidence_s3_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    evidence_text: Mapped[Optional[str]] = mapped_column(nullable=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)

    organization: Mapped["Organization"] = relationship(back_populates="reports")
