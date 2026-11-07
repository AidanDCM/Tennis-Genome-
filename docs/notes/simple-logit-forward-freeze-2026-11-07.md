# Simple logistic research challenger freeze — 2026-11-07

Four inference-only, content-addressed research artifacts were trained from the retained
2010–2025 ATP/WTA yearly CSVs at pinned upstream commit
`83733587353df8a41f2fd4f516147d5aa83f5a8d`. The training script is
`scripts/freeze_simple_logit_challenger.py`. The source manifests retain SHA-256 for
every input CSV; each model artifact retains its training-population hash, feature order,
scaling, coefficients, training end, and semantic hash. The historical source has
research-only licensing and target-row T0 limitations. None of these artifacts is
production eligible.

| Artifact | Training rows | Last training date | Semantic SHA-256 |
| --- | ---: | --- | --- |
| ATP BASE | 43,885 | 2025-12-17 | `c292435037331f92eedcf1becc4b68d1d3cc7d40693b608e2f2e0c200b4586be` |
| ATP RANK | 43,031 | 2025-12-17 | `322fb6f41f293969dd970b520f98e920f3568e49b8fbbcfa0c35e676c8680a76` |
| WTA BASE | 41,145 | 2025-11-01 | `bf4afc269cc5f449018a6608dea3a9996df695bd01f8b7b1250b9cc1690d8039` |
| WTA RANK | 39,783 | 2025-11-01 | `4b9144900219775ad41fc1cab87b8c485f84670cacd8d11ab1bd16d9ee323c1f` |

## First linked paper forecast

The Hong Kong WTA final fixture `web:wta:1074:2026:LS001` is scheduled for
2026-11-08 16:00 +08:00 (03:00 America/New_York). The retained [Web Shadow Slate
run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42376160764) was
created 2026-11-07 13:15:58 UTC. Its source artifact `13575862170` was created
13:17:10 UTC. The challenger reused its exact matchup input, whose SHA-256 matches
the previously frozen Genome prediction. No new tennis provider request was made.

The BASE challenger record was created 2026-11-07 21:13:18 UTC, selecting Alexandra
Eala with probability **0.654873**. The existing Web Shadow Genome probability for
Eala is **0.608564**. The BASE record SHA-256 is
`c08930790279ec12c1b23c583e3a02cf21bb069c4c8c608c3ee2e1801bebecc6`.

An existing [November 2 API-Tennis standings
artifact](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41513797254) and
[Hong Kong player-profile artifact](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41514115221)
were separately downloaded. Their raw and manifest SHA-256 values match retained GitHub
receipts. Full names, provider IDs and birthdates bind Claire Liu and Alexandra Eala to
the fixture's canonical identities. The observed standings values were Liu rank 109,
691 points and Eala rank 19, 2,241 points. This is a **November 2 observed snapshot**;
its ranking effective date is not asserted. The reviewed rank-evidence record SHA-256 is
`47d36b89b8648d689a2076b0d51865082c3540458ec9dcba335d8e8cd18066d4`.
It leaves the original frozen target state untouched.

The RANK challenger record was created 2026-11-07 21:17:45 UTC, also selecting
Alexandra Eala, with probability **0.715922**. Its record SHA-256 is
`1dd5c2bb8ccc928a532be401ea66d9caecdb09031f4aafe9c9a11501f21e4ba2`.
Both challenger records bind their model, matchup, target state, fixture, canonical
player IDs, existing prediction, source run, artifact ID and schedule. The RANK
record also binds the reviewed standings evidence.

This is a paper-only stale-history comparison. Actual start is not yet verified, and
the GitHub commit time is the external pre-start commitment to inspect later. It
does not count in `FULL-STACK-FORWARD-001`. The retained target state has no ranks;
the RANK arm uses only the separately retained and validated earlier snapshot.

After the match, settle all three predictions on the same verified winner and record
paired Brier and log loss. One match cannot decide model quality. For future RANK
forecasts, obtain a fresh pre-start ranking snapshot with verified canonical IDs,
both rankings and points, source time and hash. Also qualify
current player history to remove the June 2 state cutoff before treating a
challenger comparison as representative of the intended live engine.
