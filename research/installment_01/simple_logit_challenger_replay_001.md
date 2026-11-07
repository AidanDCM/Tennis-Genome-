# Simple logistic challenger: exploratory paired replay 001

This is a **development result**, not independent confirmation. The candidate feature
choices were made after the partial-2026 Core holdout was opened. Historical target-match
ranking and ranking-points values are `RESEARCH_ONLY_UNVERIFIED` for exact T0 availability.
Other completed-row target context is likewise not fully timestamp-verified. This source is
research-only under its CC BY-NC-SA 4.0 terms and is not commercial input approval.

The reproducible entry point is `scripts/evaluate_simple_logit_challenger.py`. It reads the
locally retained 2010–2025 ATP/WTA yearly Sackmann-style CSVs pinned to upstream commit
`83733587353df8a41f2fd4f516147d5aa83f5a8d`, filters to scored matches without
retirement or walkover, builds prior-date canonical foundational state, fits separate ATP
and WTA models through 2020, and scores 2023–2025. It skips 2021–2022 as an unused gap,
not as a protected test. The script prints SHA-256 for every source file. It makes no
provider request. The Core column uses the repo's strict A feature set **refit on the
same 2010–2020 rows**, not the sealed production coefficients or the 2026 holdout.

On every row of a comparison, models use the identical canonical match ID and outcome.
The rank-complete comparison restricts **all three models** to the same rows with both
players' positive rank and points. All values below are means; lower Brier and log loss
are better.

| Tour and population | Model | N | Accuracy | Brier | Log loss |
| --- | --- | ---: | ---: | ---: | ---: |
| ATP all | Refit Strict Core | 8,678 | 65.35% | .21437 | .62072 |
| ATP all | Simple BASE | 8,678 | 64.59% | .21560 | .61919 |
| ATP rank complete | Refit Strict Core | 8,528 | 65.27% | .21436 | .61685 |
| ATP rank complete | Simple BASE | 8,528 | 64.61% | .21535 | .61843 |
| ATP rank complete | Simple RANK | 8,528 | 65.37% | .21348 | .61447 |
| WTA all | Refit Strict Core | 8,003 | 65.48% | .21399 | .61574 |
| WTA all | Simple BASE | 8,003 | 65.79% | .21308 | .61410 |
| WTA rank complete | Refit Strict Core | 7,888 | 65.39% | .21409 | .61586 |
| WTA rank complete | Simple BASE | 7,888 | 65.86% | .21275 | .61332 |
| WTA rank complete | Simple RANK | 7,888 | 65.95% | .21050 | .60766 |

The BASE arm has mixed ATP results and small WTA gains. The RANK arm improves proper
scores in this exploratory replay, but its source availability is unresolved and it does
not establish a prospective improvement. There is no uncertainty interval or predeclared
promotion test for these already inspected development results. The next valid test is a
frozen, paired future comparison with current legally captured player state and ranking
snapshots, recording coverage and failures as well as scores.
