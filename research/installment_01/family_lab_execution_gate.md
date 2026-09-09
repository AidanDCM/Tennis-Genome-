# Foundational Family Lab — Exact-Head Execution Gate

This gate was committed before reading or classifying any completed foundational-family result.

An accepted `FOUNDATIONAL-FAMILY-LAB-001` artifact must satisfy all of the following:

1. The branch head includes the pre-registered contract in `foundational_family_lab.md`.
2. The branch head includes all canonical-v3 source mappings and family definitions used by the run.
3. The branch head includes regression tests covering same-date freezing, source A/B orientation, workload missingness, long rest gaps, and legacy WTA seed/entry normalization.
4. Normal CI on the same source/test state must pass Ruff and Pytest.
5. ATP and WTA canonical-v3 builds must both pass before modeling.
6. EXP-001, EXP-002, and EXP-003 reruns are regression gates and must complete before the family laboratory.
7. ATP and WTA family reports must come from the same workflow run and pinned historical source snapshot.
8. Only artifacts uploaded by that successful workflow run may be used for family classification.
9. Post-result findings must be written to a separate findings document; the preregistration files are not rewritten to fit the observed result.
10. A later findings-only commit does not invalidate the accepted artifact because it cannot alter the source data, feature construction, model, or scoring logic used by the run.

The legacy seed normalization tests are part of the required exact-head evidence because the WTA research snapshot contains historical seed/entry conventions that must be normalized without silently coercing unknown tokens.
