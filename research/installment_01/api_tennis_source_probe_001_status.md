# API-Tennis Source Probe 001 Status

Status: IMPLEMENTED ON FEATURE BRANCH / AWAITING CI AND MAIN-BRANCH ONE-CALL EXECUTION

Frozen provider request budget: 1

Requested fixtures date: 2026-09-16 UTC

The probe is deliberately non-promotional. It cannot alter the production champion and cannot admit API-Tennis scheduled `event_time` as exact historical start chronology. The only permitted live execution is the single request registered in `.github/api-tennis-source-probe-request.json` after the implementation passes repository CI and is merged to `main`.

Next step after CI: merge, execute exactly one provider request, retain the raw artifact, and classify API-Tennis by the evidence it actually exposes before any wider request budget is authorized.
