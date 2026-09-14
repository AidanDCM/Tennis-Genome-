# Research lifecycle ledger

Status: **authoritative chronological black-box record for new Workbench campaigns**

Content-addressed definitions answer **what object is this?** They do not answer **what
happened first?**

The `ResearchLifecycleLedger` adds that missing chronological record without replacing
the immutable content registry.

## Recorded lifecycle

The ledger can record:

1. procedure registration;
2. evaluation registration;
3. search-family registration;
4. search-family freeze;
5. irreversible protected-data opening;
6. canonical result recording;
7. evaluation closure;
8. later invalidation when an analysis defect is discovered.

Each event is:

- immutable;
- one atomic file;
- sequence-numbered;
- linked to the previous event hash;
- content-addressed;
- replayed semantically during verification.

An empty ledger reports `EMPTY`, not `PASS`.

## Semantic replay rules

Replay fails when, among other things:

- an evaluation references an unregistered procedure;
- a search family references an unregistered procedure;
- a search family changes while being frozen;
- protected evidence is opened twice;
- the protected-open receipt lacks an irreversible credential-enforced boundary;
- a protected result appears before the protected opening;
- a result is not bound to a frozen registered search family;
- a result's procedure/evaluation hashes disagree with registered definitions;
- a procedure result appears twice;
- a result appears after evaluation closure;
- an evaluation closes before every registered procedure has a result;
- an evaluation is invalidated before it is closed;
- any historical event or hash-chain link is rewritten.

## Negative evidence

Closure is append-only. A `NO_IMPROVEMENT` or `FAILED` result remains in history.

If a later audit discovers an implementation defect, the evaluation receives a later
`EVALUATION_INVALIDATED` event. The original close event is not rewritten.

This distinction preserves both facts:

- what the research process concluded at the time;
- why that conclusion later ceased to be scientifically usable.

## Concurrency / crash behavior

Writers acquire an exclusive creation lock. Events are written to temporary files,
fsync'd, and atomically renamed into the event directory. A failed semantic transition is
rejected before an event is written.

This ledger is research-only. It has no prediction-production, market, wagering, or
real-money authority.
