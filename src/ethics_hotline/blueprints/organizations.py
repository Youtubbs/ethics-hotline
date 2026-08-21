"""Organizations blueprint: register, list, update, and delete organizations."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import func, select

from ethics_hotline.errors import ConflictError, NotFoundError
from ethics_hotline.models import Organization, Report, db
from ethics_hotline.schemas import (
    OrganizationCreate,
    OrganizationDeleteConfirm,
    OrganizationRead,
    OrganizationUpdate,
)

organizations_bp = Blueprint("organizations", __name__, url_prefix="/organizations")


def _get_organization_or_404(org_id: int) -> Organization:
    """Fetch an organization by id, raising NotFoundError if it does not exist."""
    org = db.session.get(Organization, org_id)
    if org is None:
        raise NotFoundError(f"Organization {org_id} not found.")
    return org


def _serialize_organization(org: Organization, open_report_count: int) -> dict:
    """Render an Organization row as the OrganizationRead JSON shape."""
    return OrganizationRead(
        id=org.id,
        name=org.name,
        industry=org.industry,
        created_at=org.created_at,
        open_report_count=open_report_count,
    ).model_dump(mode="json")


@organizations_bp.post("")
def create_organization() -> tuple[Response, int]:
    """Register a new organization."""
    payload = OrganizationCreate.model_validate(request.get_json(silent=True) or {})
    org = Organization(name=payload.name, industry=payload.industry)
    db.session.add(org)
    db.session.commit()
    return jsonify(_serialize_organization(org, open_report_count=0)), 201


@organizations_bp.get("")
def list_organizations() -> tuple[Response, int]:
    """List organizations with their open (not closed) report count."""
    open_report_count = func.count(Report.id).filter(Report.status != "closed")
    stmt = (
        select(Organization, open_report_count.label("open_report_count"))
        .outerjoin(Report, Report.organization_id == Organization.id)
        .group_by(Organization.id)
        .order_by(Organization.id)
    )
    rows = db.session.execute(stmt).all()
    return jsonify([_serialize_organization(org, count) for org, count in rows]), 200


@organizations_bp.patch("/<int:org_id>")
def update_organization(org_id: int) -> tuple[Response, int]:
    """Partially update an organization's name or industry."""
    org = _get_organization_or_404(org_id)
    payload = OrganizationUpdate.model_validate(request.get_json(silent=True) or {})
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(org, field, value)
    db.session.commit()

    open_report_count = db.session.scalar(
        select(func.count(Report.id)).where(
            Report.organization_id == org.id, Report.status != "closed"
        )
    )
    return jsonify(_serialize_organization(org, open_report_count or 0)), 200


@organizations_bp.delete("/<int:org_id>")
def delete_organization(org_id: int) -> tuple[Response, int]:
    """Delete an organization, cascading to its reports.

    Requires the organization id to be echoed in the request body as
    confirmation; a mismatch is a 409, not a 422, since the request is
    well-formed but disagrees with the URL about which resource to delete.
    """
    payload = OrganizationDeleteConfirm.model_validate(
        request.get_json(silent=True) or {}
    )
    if payload.id != org_id:
        raise ConflictError(
            f"Confirmation id {payload.id} does not match organization id {org_id}."
        )

    org = _get_organization_or_404(org_id)
    db.session.delete(org)
    db.session.commit()
    return "", 204
