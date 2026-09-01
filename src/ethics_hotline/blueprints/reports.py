"""Reports blueprint: submit, list, update status, and delete reports.

Nested under an organization (/organizations/<org_id>/reports/...), which
is also where the summary route added in a later pass will live. All
mutation logic lives in services/reports.py; routes only parse the
request, build any AWS wrapper a service needs from the shared session
module, and translate the result to JSON. No route calls boto3.client()
directly.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from ethics_hotline.aws.comprehend import ComprehendClient
from ethics_hotline.aws.session import get_session
from ethics_hotline.errors import ConflictError
from ethics_hotline.models import Report
from ethics_hotline.schemas import (
    ReportCreate,
    ReportDeleteConfirm,
    ReportListQuery,
    ReportRead,
    ReportStatusUpdate,
)
from ethics_hotline.services.reports import (
    delete_report,
    list_reports,
    submit_report,
    summarize_reports,
    update_report_status,
)

reports_bp = Blueprint(
    "reports", __name__, url_prefix="/organizations/<int:org_id>/reports"
)


def _serialize_report(report: Report) -> dict:
    """Render a Report row as the ReportRead JSON shape."""
    return ReportRead.model_validate(report).model_dump(mode="json")


@reports_bp.post("")
def create_report(org_id: int) -> tuple[Response, int]:
    """Submit a new anonymous report against an organization."""
    payload = ReportCreate.model_validate(request.get_json(silent=True) or {})
    comprehend = ComprehendClient(get_session())
    report = submit_report(org_id, payload, comprehend)
    return jsonify(_serialize_report(report)), 201


@reports_bp.get("")
def get_reports(org_id: int) -> tuple[Response, int]:
    """List an organization's reports, filtered and sorted by query params."""
    query = ReportListQuery.model_validate(request.args.to_dict())
    reports = list_reports(org_id, query)
    return jsonify([_serialize_report(r) for r in reports]), 200


@reports_bp.get("/summary")
def get_reports_summary(org_id: int) -> tuple[Response, int]:
    """Return report counts for an organization, by category and by status."""
    return jsonify(summarize_reports(org_id)), 200


@reports_bp.patch("/<int:report_id>")
def patch_report_status(org_id: int, report_id: int) -> tuple[Response, int]:
    """Move a report to a new status, subject to transition rules and locking."""
    payload = ReportStatusUpdate.model_validate(request.get_json(silent=True) or {})
    report = update_report_status(org_id, report_id, payload)
    return jsonify(_serialize_report(report)), 200


@reports_bp.delete("/<int:report_id>")
def remove_report(org_id: int, report_id: int) -> tuple[Response, int]:
    """Delete a report; requires an admin marker and the report id echoed back."""
    payload = ReportDeleteConfirm.model_validate(request.get_json(silent=True) or {})
    if payload.confirm_id != report_id:
        raise ConflictError(
            f"Confirmation id {payload.confirm_id} does not match report id {report_id}."
        )
    delete_report(org_id, report_id)
    return "", 204
