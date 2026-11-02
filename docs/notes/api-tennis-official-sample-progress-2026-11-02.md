# Fixed official-stat sample: review progress

`scripts/audit_api_tennis_official_sample_progress.py` reconciles the frozen,
deterministically selected 28-match source-check sample against retained
official-stat adjudications and the verified identity audit. It checks capture
hash agreement, duplicate or contradictory reviews, player IDs, point-gate
status, and reported agreement arithmetic. It does not select replacement
matches or make provider requests. The detailed research-only queue is retained
locally at `outputs/api-tennis-official-sample-progress-2026-11-02-verified.json`.

| Fixed sample | ATP | WTA | Total |
| --- | ---: | ---: | ---: |
| Reviewed; both players' service points won/played agree | 2 | 6 | 8 |
| Pending official-stat review | 12 | 8 | 20 |
| Total selected | 14 | 14 | 28 |

Among the 20 pending cases, 14 have both players' exact full-name/birthdate
identity candidates, three have a name-only or mixed identity tier, and three
remain unresolved. The sample includes Laver Cup and Billie Jean King Cup
fixtures, so a later source-quality estimate for the frozen main-tour
population must explicitly separate those events and any qualifiers. The
sample must not be silently narrowed after inspecting results.

The eight agreeing reviews inspect **service points won and played for each
player**, not all serve/return fields used by the model. The official values
were manually transcribed into curated source references; this reconciliation
does not authenticate the linked pages at runtime. Eight of 28 reviewed is
progress, not a pass rate or broad source admission. The 20 pending remain in
the denominator, and production source admission remains closed.

Next: complete the fixed sample against official ATP/WTA/tournament statistics
where exact counts are published, mark genuinely unavailable cases as such, and
compare each completed review with the internal point gate. The separate
current-state and verified actual-start requirements still govern any live
full-stack forecast. No frozen model or forward protocol was changed.
