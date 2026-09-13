# PATTERN-CONFIRM-001 Pre-result Amendment 007 — The Odds API Credential Transport Exception

Status: **frozen while prospective N = 0, before any credentialed provider dry run, and before any eligible post-cutoff outcome is inspected**

Amendment 003 correctly required provider credentials to remain secret, but its Section 4 wording also said credentials must never appear in URLs. The official The Odds API v4 contract requires authentication through an `apiKey` query parameter. Its documented Sports and Odds endpoints use `?apiKey=...`, and its documented `MISSING_KEY` error states that the `apiKey` query parameter is required.

No real provider credential has been used by this project at the time of this correction. No prospective row or provider-result observation has been spent. This is therefore an objective transport-contract correction made before the affected path is exercised with real credentials.

Official references checked before this amendment:

- The Odds API v4 documentation: `https://the-odds-api.com/liveapi/guides/v4/`
- The Odds API v4 error documentation: `https://the-odds-api.com/liveapi/guides/v4/api-error-codes.html`

## 1. Narrow exception

For `THE_ODDS_API_V4_PINNACLE_V1`, the API key may exist in memory as the provider-required `apiKey` query parameter of the outbound HTTPS request sent directly to `https://api.the-odds-api.com`.

This exception exists only because the frozen provider requires query-parameter authentication. It does not authorize any broader credential exposure.

## 2. Persistence and observability prohibition

A real The Odds API credential may not be:

- committed to the repository;
- written into a report, research artifact, provider snapshot, source package or ledger;
- written into application logs or CI logs;
- included in an exception/error message;
- stored in a persisted request URL or request-history artifact;
- printed to stdout/stderr;
- included in a test fixture or example as a real credential.

The code may use obvious dummy strings in unit tests solely to verify redaction/non-serialization behavior.

## 3. Error handling

If a request fails, any diagnostic URL must remove the query string before it is emitted. Provider response bodies may be retained only where the existing outcome-blind dry-run contract allows them and only if they contain no credential material.

## 4. Secrets source

Credentialed execution continues to read the The Odds API key only from the runtime environment/secret store. The key is not a model input and cannot influence event selection except through provider authentication itself.

## 5. Scientific contract unchanged

This amendment changes no hypothesis, signal, correction, alpha, O'Brien-Fleming boundary, look N, identity rule, state rule, Pinnacle requirement, timing gate or readiness threshold. It only makes the frozen transport contract consistent with the provider's documented authentication mechanism while preserving the original secrecy intent.

`PATTERN-CONFIRM-001` remains `ACCUMULATING, N=0` for both selected hypotheses.
