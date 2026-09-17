# API-Tennis Source Admission Probe 001

## Purpose

Evaluate API-Tennis as a secondary market-blind tennis evidence source while conserving trial request capacity.

## Frozen request budget

- Exactly one provider request.
- Endpoint family: fixtures only (`get_fixtures`).
- Requested UTC date: 2026-09-16.
- No polling.
- No odds or market endpoint.
- No automatic follow-up requests.

## Scientific interpretation

`event_date` / `event_time` are treated as schedule metadata and are not admissible as historical actual-start chronology by default. The probe inventories any distinct actual-start-like fields but cannot promote chronology from scheduled time.

Potential supported roles are evaluated from the retained response:

- historical fixture identity;
- historical terminal outcome;
- point-by-point data when present;
- serve/return statistics when present;
- current-tournament state support.

Historical actual-start chronology remains excluded unless separately proved by a source contract and independent audit.

## Safety and provenance

The raw response is retained byte-for-byte and SHA-256 bound. The API key is never written to an artifact. The parser fails closed if fixture payloads unexpectedly contain market/odds fields. The GitHub workflow must execute from `main`, preserve an explicit one-request count, and upload a provenance receipt with the workflow source SHA.

## Promotion rule

This probe cannot modify `TGE-Independent-v1`. Any future API-Tennis feature family must enter only as a versioned research/challenger source and earn promotion under the Champion–Challenger protocol.
