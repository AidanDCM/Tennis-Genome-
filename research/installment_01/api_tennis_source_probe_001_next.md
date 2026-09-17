# API-Tennis Source Probe 001 — Next

1. Open PR from `dev/api-tennis-source-audit-v1` to `main`.
2. Require repository CI to pass.
3. Merge only after CI passes.
4. Main-branch merge triggers exactly one `get_fixtures` request for 2026-09-16 UTC.
5. Inspect retained raw response and audit artifact.
6. Approve only evidence roles actually supported by the response.
7. Do not authorize broader API-Tennis usage until a bounded adapter plan exists.
