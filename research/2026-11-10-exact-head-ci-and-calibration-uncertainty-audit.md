# Iteration 21 — 2026-11-10: verified exact-head CI; sensitivity artifact execution blocker

Research-only; no champion or settlement modification. Inspected repository default branch main, draft PR #429 head cbe30ff99e95bd93a58eb44dd218ce2168d839ae, and acquisition PR #428 head e676c961d674ffd32d254bb96f738ae7242e211f.

## Executed and verified
- GitHub CI on exact PR head cbe30ff99e95bd93a58eb44dd218ce2168d839ae: run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42817458970, completed success. Job 129834065331: Ruff success, Pytest success. Only artifact returned is ci-diagnostics, not research-date-cluster-sensitivity.
- Source inspected: scripts/research_calibration_signflip_real.py blob 611daf2912a5c7fdb19e9405cccafea487a68e5b; workflow .github/workflows/research-calibration-signflip.yml blob dd9af7aa444603e8dbbe3def5d2c683d84e41f54. Script implements 15 date leave-one-out exclusions; no complete output artifact retrieved.
- Main web-shadow/scorecard.json inspected: 85 scored matches, 46 correct, Brier 0.2514610585394295, log loss 0.6969082732945988; 88 settled records; non-production only. Main active-results.json blob 52d8645a3389c9b2d8ba5a6c87e520e23ab80a25 remains a different result path from unmerged PR #428.
- Independent local numerical diagnostic using scipy.stats.binomtest(46,85).proportion_ci(method='wilson'): 95% Wilson interval [0.4357633607,0.6430286818]. Difference between hit rate 46/85 and mean selected probability 0.6204236062 = -0.0792471356. The interval describes hit rate, NOT a paired calibration-effect confidence interval. Reproduce: python -c "from scipy.stats import binomtest; print(binomtest(46,85).proportion_ci(method='wilson'))".
- Local git ls-remote failed with 'Could not resolve host: github.com'; GitHub connector reads worked.

## Hypotheses and negative results
H1: Existing sensitivity workflow has a completed, downloadable numerical artifact at latest exact head. Rejected: only CI diagnostic artifact returned for run 42817458970; research script output not independently verified. A successful pytest job does not establish the script was run as a standalone research job.
H2: Current scorecard's apparent overconfidence is decisively demonstrated by observed accuracy alone. Not supported: Wilson interval for hit rate contains the mean selected probability; this is a weak descriptive check and not a formal heterogeneous-probability calibration test. Avoid treating this as evidence of no miscalibration either.

## Literature / transferable evaluation method
- Gneiting & Raftery (2007), strictly proper scoring rules, https://doi.org/10.1198/016214506000001437. Use paired Brier and log loss for genuine prospective predictions, not accuracy alone.
- Dimitriadis, Gneiting & Jordan (2021), stable reliability diagrams, https://doi.org/10.1073/pnas.2016191118. CORP can diagnose calibration on a fresh sample; fitted diagrams on reused 85 observations are exploratory.
- Ferro (2017), forecast evaluation with observation error, https://doi.org/10.1002/qj.3115. Identity mismatch makes scoring untrustworthy; do not force-match.
These methods are methodological, not external tennis accuracy benchmarks; licenses and implementations were not copied.

## Next executable queue
P0: Obtain an actual completed research-only workflow run and its full date-cluster-sensitivity.json artifact; inspect all 15 exclusions, min/max improvements and sign reversals. If workflow is not registered/triggered, investigate GitHub Actions workflow registration on main and use approved dispatch, without modifying champion.
P1: Audit acquisition PR #428's two identity conflicts against original WTA source bytes and prediction identity, without weakening trust gates; verify fresh forward aggregate N.
P2: Prespecify future untouched prospective paired challenger–champion Brier/log-loss and coverage evaluation. No model promotion.
