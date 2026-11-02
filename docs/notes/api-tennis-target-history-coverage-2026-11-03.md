# November 3 pilot target: retained-history coverage

The offline `scripts/audit_api_tennis_target_history_coverage.py` joins the
receipt-verified historical identity audit to the November 3 exact player
crosswalk. It makes **zero provider calls** and writes a local, input-hashed
report under `outputs/api-tennis-target-history-coverage-2026-11-03.json`.
Its SHA-256 is
`73fdc241d7223b0666afbb4c82c9ddf2b8715a71dc237fcea6c56d500e4777ff`.
All ten history captures stop by November 1, before the target date.

There are 36 inventoried fixtures and 29 exact two-player registry candidates.
For each player, the report counts retained matches with both players'
identities exactly resolved and internally consistent point statistics. This
is a **coverage count**, not a quality or production-admission score. Three
exact target candidates have no such retained history for at least one player.

Among WTA candidates, the largest minimum per-player counts are Gibson–
Oliynykova (24/18) and Parks–Eala (18/25), followed by Udvardy–Montgomery
(19/14). These are useful pilot targets **only if** their fixture identity,
schedule and actual pre-start status are verified again. The counts begin with
the May 3 API-Tennis window and omit earlier pinned history; they do not imply
that all matches needed for a full chronological state are available or
admitted. Point-conflicting and name-only rows remain separately counted and
are excluded from the exact-consistent count.

No production `MatchupInput` or formal prediction was made. The immediate
engineering gate remains a reviewed historical player/tournament crosswalk,
duplicate reconciliation with the pinned archive, source-quality admission
policy, chronological feature replay, and an independently verified actual
start. Do not fill those gaps by treating current standings or retrospective
captures as if they existed before earlier matches.
