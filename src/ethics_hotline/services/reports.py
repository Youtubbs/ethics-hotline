"""Service layer for report submission, listing, and lifecycle mutations.

The status-transition rule and the concurrency-control strategy
implemented here are documented in docs/decisions.md.
"""

from __future__ import annotations

from sqlalchemy import func, select, update

from ethics_hotline.aws.comprehend import ComprehendClient
from ethics_hotline.errors import ConflictError, NotFoundError
from ethics_hotline.models import Organization, Report, db
from ethics_hotline.schemas import ReportCreate, ReportListQuery, ReportStatusUpdate
from ethics_hotline.services.categorize import suggest_category
from ethics_hotline.services.screening import screen_text

# A closed report can only be reopened to under_review, never straight
# back to new; see docs/decisions.md for the reasoning.
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"under_review", "closed"},
    "under_review": {"closed"},
    "closed": {"under_review"},
}


def get_organization_or_404(org_id: int) -> Organization:
    """Fetch an organization by id, raising NotFoundError if it does not exist."""
    org = db.session.get(Organization, org_id)
    if org is None:
        raise NotFoundError(f"Organization {org_id} not found.")
    return org


def get_report_or_404(org_id: int, report_id: int) -> Report:
    """Fetch a report scoped to its organization, raising NotFoundError otherwise."""
    report = db.session.scalar(
        select(Report).where(Report.id == report_id, Report.organization_id == org_id)
    )
    if report is None:
        raise NotFoundError(f"Report {report_id} not found.")
    return report


def submit_report(org_id: int, payload: ReportCreate, comprehend: ComprehendClient) -> Report:
    """Screen, persist, and return a new report.

    Screening runs before the Report is constructed, so a Comprehend
    failure (raised as UpstreamAIError by the wrapper) propagates out
    before anything is added to the session. Only redacted text is ever
    written to the row.

    When the submitter supplies no category, a suggestion is derived from
    the redacted text, never the original. A supplied category is left
    alone and costs no extra Comprehend call.
    """
    get_organization_or_404(org_id)

    screened = screen_text(payload.text, comprehend)

    suggested = None
    if payload.category is None:
        suggested = suggest_category(screened.text, comprehend)

    report = Report(
        organization_id=org_id,
        text=screened.text,
        contained_pii=screened.contained_pii,
        category=payload.category,
        suggested_category=suggested,
        status="new",
        version=1,
    )
    db.session.add(report)
    db.session.commit()
    return report


def list_reports(org_id: int, query: ReportListQuery) -> list[Report]:
    """List an organization's reports, filtered and sorted by the given query."""
    get_organization_or_404(org_id)

    stmt = select(Report).where(Report.organization_id == org_id)
    if query.category is not None:
        stmt = stmt.where(Report.category == query.category)
    if query.status is not None:
        stmt = stmt.where(Report.status == query.status)
    if query.since is not None:
        stmt = stmt.where(Report.submitted_at >= query.since)

    stmt = stmt.order_by(
        Report.submitted_at.desc()
        if query.sort == "-submitted_at"
        else Report.submitted_at.asc()
    )
    return list(db.session.scalars(stmt).all())


def update_report_status(org_id: int, report_id: int, payload: ReportStatusUpdate) -> Report:
    """Apply a status transition, enforcing legal transitions and optimistic locking.

    The update is issued as UPDATE ... WHERE version = <sent version>, so
    of two concurrent status updates only the one that still matches the
    row's version can win; the loser gets a 409. If the report was
    deleted out from under the request instead, that is reported as a
    404, not a 409.
    """
    report = get_report_or_404(org_id, report_id)

    if payload.status not in ALLOWED_STATUS_TRANSITIONS.get(report.status, set()):
        raise ConflictError(
            f"Cannot transition report {report_id} from {report.status} to {payload.status}."
        )

    result = db.session.execute(
        update(Report)
        .where(Report.id == report_id, Report.version == payload.version)
        .values(status=payload.status, version=Report.version + 1)
    )

    if result.rowcount == 0:
        db.session.rollback()
        if db.session.get(Report, report_id) is None:
            raise NotFoundError(f"Report {report_id} not found.")
        raise ConflictError(
            f"Report {report_id} was modified by another request; refetch and retry."
        )

    db.session.commit()
    db.session.refresh(report)
    return report


def delete_report(org_id: int, report_id: int) -> None:
    """Delete a report."""
    report = get_report_or_404(org_id, report_id)
    db.session.delete(report)
    db.session.commit()


def summarize_reports(org_id: int) -> dict[str, dict[str, int]]:
    """Return an organization's report counts by category and by status.

    Both breakdowns are GROUP BY aggregates, not Python loops over rows.
    The category breakdown reports the effective category: the submitted
    one when present, otherwise the suggested one.
    """
    get_organization_or_404(org_id)

    effective_category = func.coalesce(Report.category, Report.suggested_category)

    by_category_rows = db.session.execute(
        select(effective_category, func.count(Report.id))
        .where(Report.organization_id == org_id)
        .group_by(effective_category)
    ).all()

    by_status_rows = db.session.execute(
        select(Report.status, func.count(Report.id))
        .where(Report.organization_id == org_id)
        .group_by(Report.status)
    ).all()

    return {
        "by_category": {(category or "other"): count for category, count in by_category_rows},
        "by_status": {status: count for status, count in by_status_rows},
    }
