# Ethics and Compliance Hotline Intake

An anonymous ethics-hotline intake backend. Reports are screened for PII
through Amazon Comprehend before they are ever stored, categorized from
their own content, and any attached evidence is run through Amazon
Textract and screened the same way.

Flask 3, Pydantic v2, SQLAlchemy 2.0, Flask-Migrate, Postgres, structlog,
boto3, pytest, Docker.

## Install

```
cp .env.example .env
```

Then fill in `.env` (see [Configuration](#configuration)).

## Run

```
docker compose up --build
```

That brings up Postgres, waits for its health check, applies migrations,
and serves on `http://localhost:8000`. Check it with `GET /live`.

## Test

```
docker compose run --rm tests
```

Builds a test image, applies migrations, and runs the suite against a
real Postgres. Every AWS call is replaced with a double, so this needs no
AWS credentials and never reaches AWS.

## Configuration

Everything is read through .env. `DATABASE_URL` is the only technically required value.

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Postgres connection string. Required. |
| `APP_ENV`, `LOG_LEVEL` | Runtime environment and log level. |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Used by compose to build the db service and the api service connection string. |
| `AWS_REGION` | Defaults to `us-east-1`. |
| `AWS_S3_BUCKET` | Evidence bucket name. Required only for evidence uploads. |
| `MAX_EVIDENCE_BYTES` | Largest accepted evidence file. Defaults to 5 MB. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Read by boto3 itself, never by this code. |

Credentials belong in `.env` and nowhere else. `.env` is gitignored.

## AWS setup

Working in `us-east-1`, create by hand in the console:

1. An S3 bucket for evidence, with all public access blocked.
2. A dedicated IAM user with a customer-managed policy granting exactly
   `comprehend:DetectPiiEntities`, `comprehend:DetectKeyPhrases`,
   `textract:DetectDocumentText`, and `s3:PutObject` / `s3:GetObject`
   scoped to that one bucket ARN. See [docs/IAM_user.json.example](docs/IAM_user.json.example) to see a sample permission json.
3. Access keys for that user, pasted into `.env` only.

## API

| Method | Path |
| --- | --- |
| GET | `/live`, `/ready` |
| POST, GET | `/organizations` |
| PATCH, DELETE | `/organizations/<id>` |
| POST, GET | `/organizations/<id>/reports` |
| GET | `/organizations/<id>/reports/summary` |
| PATCH, DELETE | `/organizations/<id>/reports/<report_id>` |

Submitting with evidence uses `multipart/form-data` with an `evidence`
file field; without evidence, plain JSON works. Every error returns
`{"error": {"code", "message"}, "request_id"}`.

## Documentation

- [docs/decisions.md](docs/decisions.md) — every major design decision for edge cases and its reasoning
- [docs/architecture.md](docs/architecture.md) — what talks to what
- [docs/erd.md](docs/erd.md) — the data model
- [docs/request-flow.md](docs/request-flow.md) — how a request moves through the app
- [docs/testing-architecture.md](docs/testing-architecture.md) — the test container and rollback-per-test fixture

## Kanban Board

Look at Projects -> [Ethics Hotline Kanban board](https://github.com/users/Youtubbs/projects/2) to see objectives completed.
