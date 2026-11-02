# API-Tennis 2026 source overlap after exact identity review

The offline audit in `scripts/audit_api_tennis_pinned_overlap.py` verifies the
retained May 3–June 2 API-Tennis capture against its GitHub receipt and raw
hashes, checks that the identity report refers to the same capture, and compares
it to the pinned 2026 Sackmann ATP/WTA main-tour archive. It makes **zero new
provider requests**. The detailed report is retained locally at
`outputs/api-tennis-pinned-overlap-audit-2026-11-02.json`; raw provider records
remain outside the public repository pending license review.

The join requires both players to have exact full-name/birthdate identity
candidates, the same winner, a unique player pair, a reviewed tournament-name
equivalence, and the API event date to fall from the pinned tournament start
through 28 days later. Only exact eight-field comparisons are scored: both
players' service-point totals, first serves in, first-serve points won, and
second-serve points won. This is a retrospective source comparison, not a
pre-match prediction.

| May 3–June 2 capture, 910 fixtures | Count |
| --- | ---: |
| All eight fields agree, API points internally consistent | 149 |
| Eight fields disagree, API points internally conflicting | 36 |
| Internal API point conflict, pinned fields incomplete | 16 |
| API points consistent, pinned fields incomplete | 149 |
| Joined but API point stats unusable | 60 |
| Both exact identity unavailable | 217 |
| No unique, reviewed tournament join | 247 |
| Not finished | 36 |

The 149 complete, internally consistent matches comprise 83 ATP and 66 WTA.
All eight fields agree in each. The 36 complete conflicting matches comprise
17 ATP and 19 WTA; all disagree with the pinned archive in at least one field.
That is strong evidence that the internal point-consistency quarantine is
useful in this overlap, but the conditional sample is small and selected. It
does not prove that all later API-Tennis records are accurate, that both sources
are independent, or that API-Tennis history is safe to feed into production.

The previous loose-name overlap audit found 49 disagreements in 282 complete
joins. Its sample and join criteria differ; these two counts must not be
subtracted or presented as a before/after error-rate estimate.

**Admission remains closed.** The next high-value work is to review a fixed
official-stat sample outside this pinned overlap and independently confirm
historical surface and population. For live forecasts, the system still needs
time-legal current player state and verified actual-start evidence. The frozen
calculator and FULL-STACK-FORWARD protocol are unchanged.
