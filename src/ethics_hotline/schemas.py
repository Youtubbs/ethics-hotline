"""Pydantic v2 schemas for HTTP request/response.

These are the only place field-level constraints (Literal categories and
statuses, report-text length) are enforced before data reaches the ORM
layer in 'models.py'.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["safety", "harassment", "financial", "other"]
Status = Literal["new", "under_review", "closed"]

# Provisional bounds for report text. The lower bound exists so Comprehend
# never sees empty or single-character input; its final justified value is
# set later, which may adjust this constant.
REPORT_TEXT_MIN_LENGTH = 20
REPORT_TEXT_MAX_LENGTH = 5000


class OrganizationCreate(BaseModel):
    """Payload to register a new organization."""

    name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=200)


class OrganizationUpdate(BaseModel):
    """Payload to partially update an organization's name or industry."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    industry: Optional[str] = Field(default=None, min_length=1, max_length=200)


class OrganizationDeleteConfirm(BaseModel):
    """Payload confirming deletion of an organization by echoing its id."""

    id: int


class OrganizationRead(BaseModel):
    """An organization as returned to clients, including its open-report count."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry: str
    created_at: datetime
    open_report_count: int = 0


class ReportCreate(BaseModel):
    """Payload to submit a new anonymous report."""

    text: str = Field(min_length=REPORT_TEXT_MIN_LENGTH, max_length=REPORT_TEXT_MAX_LENGTH)
    category: Optional[Category] = None


class ReportStatusUpdate(BaseModel):
    """Payload to move a report to a new status."""

    status: Status


class ReportRead(BaseModel):
    """A report as returned to clients (redacted text only, never the raw submission)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    text: str
    contained_pii: bool
    category: Optional[Category]
    suggested_category: Optional[Category]
    status: Status
    submitted_at: datetime
    evidence_text: Optional[str]
