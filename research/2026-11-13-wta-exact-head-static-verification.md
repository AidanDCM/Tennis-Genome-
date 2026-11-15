# 2026-11-13 WTA exact-head static verification (read-only)

## Baseline and hypothesis
PR #479 head `46b56da3dfa9d752a70288d3c151c4997789bb32`, main baseline `40bb697ec786527b7ed1a4c67d6d0a92aea17782`.
Hypothesis: the last E501 correction removes all >100-character lines from the nine-case test module without removing or duplicating any regression case. Prespecified pass: max line length <=100, nine unique test methods, unchanged module import and textual-round assertion. This is a *static source check*, not a Ruff/pytest execution or proof of CI success.

## Actual execution and results
Connected GitHub fetch of `tests/test_wta_round_identity_diagnostic.py` at exact head, blob `0f69b0a613ac26efa44ca45956a7ecbd29e7fb6d`. JavaScript split by newline and counted line lengths and `def test_*` declarations: 51 lines; max length 99; zero lines above 100; 9 methods, all distinct; expected module import and intermediate textual-round assertion present. Static hypothesis **passed**.
Exact-head GitHub pull-request-triggered workflow lookup returned **zero runs**; combined commit status returned **zero statuses**. Neither proves no workflow was triggered outside those API scopes. CI remains **unverified**. Previous run #43353580672 on older head passed 1319 pytest cases but failed Ruff E501; no claim of green CI on current head.
No repository-wide pytest or Ruff was executed this iteration; no settlement or model logic changed.

## External research and contrary evidence
- Nanayakkara, Christen & Christen (2025), [Unsupervised Evaluation of Entity Resolution](https://doi.org/10.1145/3721985), ACM Journal of Data and Information Quality, 21 March 2025: evaluates estimated missed/false links with incomplete labels across multiple datasets; useful as *review-only* prioritization, but unverified tennis transfer, no software imported or implementation license verified.
- Maciejewski et al. (2025), [Progressive Entity Matching: A Design Space Exploration](https://doi.org/10.1145/3709715), Proceedings of the ACM on Management of Data, 10 February 2025, CC BY article; 10 record-linkage and 8 deduplication benchmarks. Progressive filtering could prioritize manual adjudication, but benchmark tuning and dataset differences forbid using its headline results as tennis evidence; no implementation imported or software license checked.
- US Census Bureau [FY2025 CSRM annual report](https://www.census.gov/content/dam/Census/library/publications/2025/adrm/2025-CSRM-Annual-Report.pdf) reports simulations where missed record matches bias downstream estimates. This is a contrary reason to track *all* unqualified predictions, not just settled scores; methods and samples differ, no tennis validation.

## Priority queue
1. Obtain and inspect exact-head full Ruff + pytest CI for `46b56da3dfa9` (or run workflow explicitly if permission/workflow allows); do not merge without verification.
2. Read main workflow and champion/forward manifests, refresh qualified denominators and shadow scorecard independently.
3. Human-adjudicate twelve legacy round-discrepant candidates with source identity, pre-start provenance and timing; keep pending until approved.
4. Add read-only mismatch reason classification and adversarial negative controls; keep settlement gates frozen.
5. After new qualified prospective observations, preregister chronological paired probability scores against frozen champion and simple baselines.
