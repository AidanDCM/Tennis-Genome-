# Historical Player Reference Availability Evidence 001

Status: **REVIEWED — canonical historical T0 availability not established**

Audit date: 2026-09-14

## Question

Can the `hand`, `height`, and `IOC` values carried in the pinned Sackmann-style historical match rows be treated as independently verified point-in-time information that was available before each target match?

## Evidence reviewed

Primary upstream references:

- https://github.com/JeffSackmann/tennis_atp
- https://github.com/JeffSackmann/tennis_wta

The upstream ATP documentation describes a **master ATP player file** whose player-reference columns include hand, birth date, country code, and height. The WTA repository likewise describes a master WTA player file containing player biographical/reference data.

Both repositories describe the yearly match-result rows as containing redundant biographical information for each player. The repositories also explicitly invite corrections and additions to missing biographical data.

Those facts establish the semantic meaning of these fields, but not historical point-in-time publication or revision semantics.

## What is established

- `hand`, `height`, and `IOC` are player-reference / biographical fields rather than post-match outcomes.
- They are copied redundantly into match-result rows in the Sackmann-style format.
- The underlying player reference tables are maintained datasets and may receive corrections or additions.
- A current or archived repository commit can reproduce the retained values at that repository version.

## What is not established

The available source contract does not provide, for each player-reference value used in each historical target row:

- a contemporaneous publication timestamp before the target match;
- a version-effective timestamp showing when a value first became known;
- a revision ledger showing whether a value was corrected after the historical match;
- evidence that redundant values in old match rows are immutable snapshots rather than retrospectively maintained copies of reference information.

This matters even for attributes that are physically stable in real life. A stable real-world trait is not the same thing as proof that the historical dataset contained the correct value at T0.

`IOC` is especially unsuitable for an assumed static-time interpretation because sporting/national representation can change during a career. Height and handedness are more physically stable, but data entry corrections and late completion of missing biography remain possible under the maintained master-file model.

## Decision

When sourced only from the pinned retrospective Sackmann-style rows, target `hand`, `height`, and `IOC` remain:

- `T0Policy.RESEARCH_ONLY_UNVERIFIED`;
- `RevisionSemantics.LATEST_ONLY_UNKNOWN_HISTORY`;
- unavailable for canonical protected-v2 target use.

No synthetic publication timestamp is assigned and no feature is promoted.

A future source may support canonical use if it provides trustworthy versioned player records or independently retained pre-match snapshots with capture timestamps.

## Scientific consequence

This is an audited negative conclusion. The fields may be useful in exploratory research, and some values are likely to have been known before many real matches, but the current historical evidence does not prove exact T0 legality strongly enough for canonical evaluation.

This review does not alter TGE-Independent-v1, the frozen historical candidate search, `FULL-STACK-FORWARD-001`, `PATTERN-CONFIRM-001`, or any prospective count.
