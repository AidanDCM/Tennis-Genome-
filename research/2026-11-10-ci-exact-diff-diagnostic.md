# 2026-11-10 CI exact-diff diagnostic and evidence audit (iteration 16)

## Reproducible observations
- Research PR #429 head before this iteration: d85f5c9a449abe6a06ec2362e16c9118585c7974; main base: 8af76720a6291b166263fa1cd8191504f84ed6b6.
- CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42777255115 (job 129698558474) **failed**: Ruff I001 at tests/test_research_calibration_signflip_real.py:7:1; pytest **1330 passed, 2 warnings**. CI steps marked success because continue-on-error, but final enforcement failed. Do not conflate step completion with check success.
- Source test file blob fd850826a57c1a2ec51be33e08b84c7ad8e2c92e. Importlib refactor did not fix I001. Local `python -m ruff --version` failed (module unavailable), and `pip install ruff` failed DNS resolution; no local Ruff test was executed.
- Diagnostic workflow change at commit 626cdedd26249b8adaaf04fc4fd769b8bfa975d5 prints `ruff check --select I --diff tests/test_research_calibration_signflip_real.py || true` in failing CI. This is *diagnostic*, not a fix, and only on the research branch. Inspect exact-head workflow before making next source change.
- Result-acquisition PR #428 snapshot wta-results-20261109t083951z: 16 pending inspected, 1 finished captured, 13 unmatched, 2 identity conflicts. Not verified as qualified settlements; do not merge without provenance review.
- Historical non-production WTA scorecard last recorded 85 scored / 46 correct (54.12%), Brier 0.251461, log loss 0.696908. Not refreshed here. Forward qualified N not established this iteration.

## Research and contrary evidence
- Buhamra, Groll and Gerharz (2025), https://doi.org/10.1177/22150218251338954: 5,013 men's Grand Slam matches 2011–2022; expanding-window validation on 2022 reportedly performed better than alternative evaluation strategies. Models and populations differ; no transfer of reported scores. Includes market features in source paper, which are explicitly **excluded** from Tennis Genome adaptations. License/reproduction rights not established; no code copied.
- Clegg & Cartlidge (2026), https://doi.org/10.48550/arXiv.2510.20454: temporal interaction graphs may carry complementary signal to weighted Elo, but the graph model alone did not improve unconditional accuracy. More complex is not necessarily better; different population, data, and validation horizon. No code copied; licensing not verified.

## Prespecified next experiment and gates
1. Read the new exact-head CI output and Ruff-generated diff; apply only the machine-suggested import formatting, then run exact-head CI and verify both lint and pytest.
2. On unchanged 55 historical research observations in 15 dates, compare fixed-half calibration vs unmodified baseline via 15 leave-one-date-out paired Brier/log-loss differences. Report full range and signs, not just best exclusion; this is sensitivity, **not** independent validation. No parameter tuning or holdout access.
3. Audit source-level identity and pre-start timestamps for PR #428; reject conflicting matches rather than backfill or weaken gates. Obtain qualified prospective N before any promotion decision.

No production change, champion promotion, settlement mutation, or claimed new predictive improvement in this iteration.
