# Ethics & Compliance Hotline Intake

## Objective

Develop an anonymous ethics-hotline intake backend for an organization's
compliance team, where employees need a genuinely safe way to report a
concern in writing — without accidentally identifying themselves or a
coworker by name in the process — and the compliance team needs incoming
reports triaged into a category fast enough to act on the urgent ones.
The system should make it easy to manage organizations and their incoming
reports, automatically screen every report for personally identifying
details via **Amazon Comprehend** before it's ever stored, and suggest a
category based on the report's actual content so nothing sits untriaged in
a generic inbox. A reporter will sometimes have supporting evidence — a
photo of a message thread, a screenshot, a scanned document — and any text
visible in it deserves the exact same PII protection as the report body,
so uploaded evidence is run through **Amazon Textract** and screened
before anything from it is stored. Prioritize correctness on the data
layer — a report's PII-screening outcome and suggested category are
explicit, queryable fields, and the *redacted* text, not the raw
submission, is what ever gets persisted once PII is detected — for the
report body and for any evidence attached to it. The deliverable is a
containerized service that runs locally via `docker compose up` and
exposes a documented REST API, backed by a real PostgreSQL database and
real (in production) calls to two AWS managed AI services.

## Functional Requirements

### Organization Management

- **Add New Organization:**
  - Compliance admins should be able to register a new organization by
    specifying its name and industry.
- **View Organizations:**
  - Provide a dashboard endpoint listing all organizations with their core
    metadata and open-report count.
- **Edit Organization:**
  - Allow updating an organization's name or industry.
- **Delete Organization:**
  - Implement deletion with a confirmation requirement (such as requiring
    the organization id in the request body). Decide (and document in
    your README) whether deleting an organization cascades to delete its reports.

### Report Management

- **Submit Report:**
  - Anyone should be able to submit an anonymous report against an
    organization by specifying free-text report content and, optionally,
    a category (`Literal["safety", "harassment", "financial", "other"]`)
    — if omitted, the system suggests one (see AI-Assisted Feature).
- **View Reports:**
  - List all reports for an organization, including their (redacted, if
    applicable) text, category, and status, with filter support by
    category and status.
- **Update Report Status:**
  - Allow a compliance officer to move a report through
    `Literal["new", "under_review", "closed"]`. Decide (and document)
    whether a closed report can be reopened, and under what conditions.
- **Delete Report:**
  - Implement an admin-only deletion path (for handling a duplicate or
    erroneous submission) with a confirmation step.
- **Attach Evidence:**
  - Accept an optional `multipart/form-data` upload (image or PDF) attached
    to a report at submission time. Store the raw file in S3 and any text
    recovered from it — after PII screening — on the report record; never
    expose the original, unscreened evidence file through the API.

### API Design & Developer Experience

- **Consistent Error Envelopes:**
  - All errors (validation, not-found, conflict, upstream AI-service
    failure) should return a consistent JSON shape with an error code,
    human-readable message, and request_id.
- **Liveness and Readiness:**
  - Expose `/live` and `/ready` endpoints. `/live` confirms the process is
    up; `/ready` confirms downstream dependencies (the database) are
    reachable. Comprehend/Textract reachability is *not* part of `/ready` —
    see Edge Case Handling below.
- **Structured Request Logging:**
  - Every request should emit a structured log line containing method,
    path, status code, duration, and correlation id, as machine-parseable JSON.
- **Filtered Listings:**
  - List endpoints should support filter + sort query parameters across
    `category`, `status`, and submission date.

### Edge Case Handling

- **Comprehend Is Unavailable:**
  - Decide how report submission behaves if PII detection or category
    suggestion fails. Given that PII screening is a safety requirement
    here (not a "nice to have"), should submission be rejected outright
    on AI-service failure rather than stored unscreened? Document your
    choice and reasoning explicitly.
- **PII Detected in a Report:**
  - Decide exactly how a detected PII span is handled — redacted in place
    before storage (with a `contained_pii` flag set), or the submission
    rejected and the reporter asked to remove identifying details. Justify
    your choice carefully in the README, given the anonymity requirement.
- **No Category Provided and No Confident Match:**
  - Decide what happens when a report's text doesn't clearly match any
    category in your keyword mapping — default to `other` rather than
    guessing confidently, and document your matching approach's known limitations.
- **Empty or Trivially Short Report:**
  - Comprehend requires non-empty input and behaves unpredictably on
    single-character text. Decide on (and enforce via Pydantic) a minimum
    report length, and document why you picked it.
- **Textract Is Unavailable, or Evidence Has No Extractable Text:**
  - Decide how a report with an attached evidence file behaves if
    extraction fails — the report body's own PII screening should not be
    blocked by a failure processing the attachment. A photo with no
    readable text at all is a legitimate outcome, not an error. Reject
    non-image/PDF uploads with a 422 and enforce a maximum file size.
- **PII Detected in Evidence Text:**
  - Apply the exact same redaction-vs-rejection policy you chose for the
    report body to any text recovered from evidence — evidence is not a
    side channel that bypasses the anonymity guarantee the rest of this
    system is built around.
- **Concurrent Mutations:**
  - Describe what happens if two compliance officers try to update the
    same report's status at the same time, or a report is deleted while
    its status is being updated. Document the expected behavior.

### AI-Assisted Feature (Required)

> **Sequencing — build this last.** This feature is a required, graded
> part of the deliverable, not an optional stretch goal. Implement it only
> after the core CRUD service is complete and working end to end — the AI
> pipeline should be layered on top of a finished functional deliverable,
> not built in parallel with it. A complete core with the AI feature added
> last scores well; an AI pipeline bolted onto an incomplete or broken core
> does not.

- **PII Screening Before Storage:**
  - Before persisting a report, call Comprehend's `DetectPiiEntities` and
    apply your Edge Case Handling decision above — this must run *before*
    the record is saved, not as an after-the-fact cleanup pass.
- **Category Suggestion:**
  - When no category is supplied, call Comprehend's `DetectKeyPhrases`
    against the (redacted, if applicable) report text and match the
    resulting phrases against a keyword mapping you define per category,
    storing the suggested category with the report.
- **Organization-Level Triage Summary:**
  - Add `GET /organizations/{id}/reports/summary` returning report counts
    broken down by category and status — the actual "nothing sits
    untriaged" payoff from the Objective, giving a compliance officer a
    fast overview instead of reading every report to figure out where
    attention is needed.
- **Evidence Text Extraction and Screening:**
  - When evidence is attached, call Textract's `DetectDocumentText`
    against the stored file, then run the recovered text through the exact
    same `DetectPiiEntities` screening path as the report body before
    storing anything from it — evidence text is never a shortcut around
    the anonymity guarantee.
- **Isolated, Mockable AWS Clients:**
  - The Comprehend and Textract calls (and S3 storage) must each go
    through their own single, injectable client module (mirroring the
    shared-session pattern from this course's Week 3 boto3 material) so
    your test suite can substitute fake/mocked clients and run without
    live AWS credentials.

## Stretch Goals

Stretch goals are features you want to add to an application, but they
aren't required. For this project, Stretch Goals are a way to go above and
beyond the minimum requirements and I look forward to seeing what unique
features you will add to your project. Here are some examples you might consider:

- **Deploy the App to AWS:**
  - Push your Docker image to Amazon ECR and run the stack on an AWS
    compute service of your choice (App Runner, ECS, or an EC2 instance).
    Document your deployment architecture and any cost/cleanup considerations.
- **Bedrock-Powered Investigation Checklist:**
  - Add an endpoint that sends a report's category and redacted text to a
    foundation model via Bedrock's Converse API and returns a suggested
    initial-investigation checklist. This uses content not yet covered in
    lecture at the time this project is assigned — a good stretch goal
    for anyone who wants to explore ahead.
- **SageMaker Custom Model:**
  - Train a simple custom model that scores report severity/urgency from
    text features beyond simple keyword matching, hosted behind a
    SageMaker endpoint. Also beyond the current curriculum — a good "go
    deeper" option.
- **Rate Limiting:**
  - Add Flask-Limiter to throttle report submissions per client IP
    (document how this interacts with anonymity expectations). Choose a
    sensible limit and document why in your README.
- **Second Entity Relationship:**
  - Extend the model to support a `FollowUpNote` entity — a compliance
    officer's internal notes on the investigation, kept separate from the
    original anonymous submission.
- **Minimal Web UI:**
  - Add a single HTML page (or React app) that consumes your API and
    displays the triage summary dashboard for a compliance officer.
- **Persistent Audit Log:**
  - Record every *administrative* mutation (status changes, deletions)
    into an audit table with timestamp, action, entity, and actor —
    deliberately excluding the original submission to preserve anonymity.
- **Bulk Import:**
  - Add an endpoint that accepts a CSV of prior-quarter reports (e.g.,
    migrated from a legacy hotline vendor) and inserts them in one
    transaction, with all-or-nothing semantics.
- **Escalation Timer:**
  - Flag reports in a `safety` category that have remained `new` for
    longer than a configurable threshold, surfaced via a `GET
    /organizations/{id}/reports/overdue` endpoint.

## Technical Requirements

Must be a backend solution consisting of:

- Python 3.11+
- Flask 3.x with the app-factory pattern and blueprints
- Pydantic v2 for HTTP-boundary validation
- PostgreSQL via SQLAlchemy 2.0 and Flask-Migrate, with a real migration
  history checked into the repo (no `create_all()` in production code paths)
- boto3, authenticated via a dedicated, least-privilege IAM user (never
  root/admin credentials) — the IAM policy JSON granting only
  `comprehend:DetectPiiEntities`, `comprehend:DetectKeyPhrases`,
  `textract:DetectDocumentText`, and `s3:PutObject`/`s3:GetObject` (scoped
  to your bucket) must be committed to the repo
- Separate, injectable client wrapper modules for Comprehend, Textract,
  and S3 — not `boto3.client(...)` called ad hoc from route handlers
- structlog for structured JSON logging with per-request correlation IDs
- pytest with fixtures and parametrize for the test suite; AWS calls must
  be mocked/stubbed in tests (e.g. `unittest.mock` or `botocore.stub.Stubber`)
  so the suite runs without live AWS credentials or network access
- Docker multi-stage Dockerfile + docker-compose.yml for a local
  api + db stack, with a database health check gating the API's startup
- pyproject.toml with a src/ layout and a `[project.optional-dependencies]` dev block
- Code should be available in a private GitHub repository, with the
  instructor added as a collaborator
- Possesses all required CRUD functionality
- Handles edge cases effectively

## Non-Functional Requirements

- Well-documented code (module docstrings + function docstrings on public surfaces)
- Code upholds industry best practices (SOLID / DRY / single-responsibility)
- Type hints on every function signature
- Test coverage on happy + error paths (at least 15 pytest tests, including
  at least one test per Comprehend- and Textract-backed endpoint using
  mocked clients)
- Structured logs (no print statements in production code paths)
- Container runnable via a single `docker compose up`
- README with one-line install and one-line run instructions, plus your
  documented decisions for every Edge Case Handling item above
- Pydantic models have explicit field constraints (Literal types, min/max
  length on report text)
- No mutable default arguments; use `field(default_factory=...)` for collections
- Errors raise typed exceptions from a DomainError hierarchy, not generic Exception
- Data model documented as an entity-relationship diagram (ERD) — every
  entity, its fields, and the cardinality of each relationship — checked
  into the repository
- A kanban board with a complete, prioritized backlog is set up **before
  development begins**; work is pulled from the board rather than started ad hoc
