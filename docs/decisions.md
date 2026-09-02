# Design decisions

Log of decisions called for by the project instructions, for the README.

## Organization deletion cascades to its reports

Deleting an organization deletes all of its reports too, instead of being
blocked while reports exist. Implemented as an ORM-level cascade
('cascade="all, delete-orphan"' on 'Organization.reports'), not a
database-level 'ON DELETE CASCADE', so no migration change was needed.

Deletion still requires the org id echoed in the request body. 

## Closed reports reopen to under_review only

Transitions: 'new' -> 'under_review' or 'closed'; 'under_review' ->
'closed'; 'closed' -> 'under_review'. Anything else, including a no-op
same-status "transition," is a 409.

Reopening should mean "someone is looking again," not "pretend it was
never closed", so it always routes back through review.

## Status updates use optimistic locking on 'version'

A 'PATCH' must include the version it last saw; the update runs as
'UPDATE ... WHERE version = :sent_version'. Zero rows affected means
either someone else updated first (409, refetch and retry) or the report
is gone (404).

Chosen over 'SELECT FOR UPDATE' because no held lock, and the failure mode is
trivial to test without coordinating two real transactions.

## PII is redacted in place

Detected PII spans are replaced with '[REDACTED]' and the report stores
with 'contained_pii' true. Screening runs before the row is built, so
the raw text is never written.

Rejecting would bounce an anonymous reporter back with "you identified
someone, try again", which discourages reporting and would encourage a second
submission that still is bad.

## Comprehend failure fails the submission closed

If 'DetectPiiEntities' fails, the submission is rejected with the
upstream error envelope (502) and nothing is written.

Screening is a safety requirement. A report stored unscreened would 
break the anonymity guarantee.

## Minimum report length is 20 characters

Enforced as a Pydantic constraint, so short text never reaches
Comprehend. Apparently, comprehend behaves unpredictably on empty or
single-character input, and 20 rules out prompts that wouldnt provide
enough context.

## Category suggestion: most keyword hits wins, otherwise other

Comprehend returns key phrases for the redacted text. Each phrase is
checked against a per-category keyword list; the category with the most
matching phrases wins

Other only runs when the submitter left the category blank, so a supplied
category is never overridden and costs no extra Comprehend call.

## Summary counts come from SQL aggregates

'GET /organizations/<id>/reports/summary' returns counts by category and
by status from two GROUP BY queries, not Python loops. The category
breakdown uses COALESCE(category, suggested_category), so an uncategorized
report is counted under whatever was suggested for it 

## Evidence is best effort

Validation rejects the submission; for example, a non-image, non-PDF upload is a 422,
and an oversized one is refused by MAX_CONTENT_LENGTH before the body is
read (413).

Past validation, nothing about the evidence can kill the report. If S3
storage, Textract extraction, or the screening of the extracted text
fails, that is logged and the report still stores with whatever
succeeded. This is the deliberate asymmetry against the body. Comprehend
failing on the body kills the submission, because an unscreened body
would break anonymity, whereas failed evidence just means less
supplementary detail.

Zero extracted text is a normal outcome, not an error. A photo with no
readable text stores with evidence_text null.

## Evidence text goes through the same redaction function as the body

process_evidence calls screen_text, the identical function the body
uses. Evidence text is stored only if it came back screened;
if screening fails, the text is dropped rather than stored unscreened.
contained_pii is true when either the body or the evidence carried PII.

## The raw evidence file is never exposed

The S3 key is stored on the row but is not part of ReportRead, so no
endpoint returns the file, the key, or a URL to it. There are no
presigned URLs anywhere.

## Max evidence size is 5 MB, from settings

MAX_EVIDENCE_BYTES in the environment, defaulting to 5242880. Textract's
synchronous DetectDocumentText caps at 10 MB, so this leaves some room
