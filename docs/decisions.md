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
