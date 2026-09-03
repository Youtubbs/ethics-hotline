# Architecture

Blue is built and working. Red (dashed) is a stretch goal that was never
started. Every required piece of the project is blue.

```mermaid
flowchart TB
    client[Client]

    subgraph shell["Application shell"]
        factory["app.py: create_app()"]
        mw["middleware.py: correlation id + request log"]
        errh["errors.py: global DomainError handler"]
    end

    subgraph routes["Blueprints"]
        health["health.py: /live /ready"]
        orgs["organizations.py: full CRUD"]
        reports["reports.py: submit, list, status, delete, summary"]
    end

    subgraph svc["Service layer"]
        reportsvc["services/reports.py: submit, list, status, delete, summarize"]
        screening["services/screening.py: screen_text redaction"]
        categorize["services/categorize.py: keyword map matching"]
        evidence["services/evidence.py: validate, store, extract, screen"]
    end

    subgraph data["Data layer"]
        models["models.py: Organization, Report"]
        migrations["migrations/: Alembic revisions"]
        pg[("Postgres")]
    end

    subgraph awslayer["AWS wrappers (injected, never built in a route)"]
        session["aws/session.py: shared boto3 session"]
        comprehend["aws/comprehend.py: DetectPiiEntities, DetectKeyPhrases"]
        textract["aws/textract.py: DetectDocumentText"]
        s3["aws/s3.py: PutObject, GetObject"]
        bucket[("S3 evidence bucket")]
    end

    subgraph notbuilt["Stretch goals, not built"]
        followup["FollowUpNote entity"]
        audit["Admin audit table"]
        csv["CSV bulk import"]
        overdue["Overdue reports endpoint"]
    end

    client --> factory
    factory --> mw --> routes
    factory --> errh
    health --> pg
    orgs --> models
    reports --> reportsvc --> models
    reports --> evidence
    reportsvc --> screening
    reportsvc --> categorize
    models --> pg
    migrations -.applies schema to.-> pg

    evidence --> screening
    screening --> comprehend
    categorize --> comprehend
    evidence --> textract
    evidence --> s3
    comprehend --> session
    textract --> session
    s3 --> session
    s3 --> bucket

    classDef implemented fill:#3b6fb6,stroke:#1f3f6e,color:#ffffff
    classDef planned fill:#c0392b,stroke:#6e1f16,color:#ffffff,stroke-dasharray: 4 3

    class client,factory,mw,errh,health,orgs,reports,reportsvc,screening,categorize,evidence,models,migrations,pg,session,comprehend,textract,s3,bucket implemented
    class followup,audit,csv,overdue planned
```

Two things the arrows are meant to make obvious:

- `screening.py` is reached from two directions, the report body and the
  evidence text, and it is the same function both times. Evidence is not
  a way around redaction.
- Routes build a wrapper from `session.py` and hand it to a service. No
  route calls `boto3.client()`, which is what lets the whole AWS layer be
  swapped for doubles in the test suite.
