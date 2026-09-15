# Trusted Sportradar prospective provider capture

`FULL-STACK-FORWARD-001` may not treat operator-supplied JSON/header files as genuine provider provenance.

The promotion-capable provider transport is frozen as:

- workflow: `.github/workflows/prospective_provider_capture_anchor.yml`
- capture schema: `full-stack-forward-trusted-sportradar-capture-v1`
- capture version: `FULL-STACK-FORWARD-001-trusted-provider-capture-v1`
- provider: Sportradar Tennis API v3 Daily Summaries
- authentication: `SPORTRADAR_API_KEY` repository secret in the HTTPS `x-api-key` header
- workflow inputs: UTC `schedule_date` plus `trial`/`production` access level only
- external ledger: issue #111, written by `github-actions[bot]`

The workflow itself fetches every Daily Summaries page, retains exact response bodies and headers, derives the pagination-v2 provider-batch ledger, derives `observed_at` from the runner clock, creates the anchor receipt, writes the public ledger commitment, and uploads the complete audit artifact.

All GitHub Actions used by the workflow are pinned to exact commit SHAs. The workflow does not install repository or third-party Python packages; it runs the repository through `PYTHONPATH=src`, and every Python invocation uses `-S` so `site`/`sitecustomize` cannot alter the trusted capture path.

Promotion verification requires all of the following:

1. the ledger comment is canonical, unedited, on issue #111, and authored by `github-actions[bot]`;
2. the referenced workflow run is a successful manual dispatch of the trusted capture workflow from `main`;
3. the run source SHA matches the receipt;
4. every capture-critical repository file at that run SHA has the exact frozen Git blob identity in `trusted_capture_provenance.py`, including package initializers and the transitive capture modules;
5. the retained batch matches the comment commitment and passes pagination-v2/provider-time verification;
6. the GitHub comment server `created_at` is not before the newest provider generation time and is no more than 30 minutes after the oldest provider generation time.

The older `.github/workflows/prospective_provider_batch_anchor.yml` hash-only workflow and local cadence-v2 fixtures remain useful for regression testing, but they are not promotion-capable evidence.

No model, feature, cohort, metric, market rule, cadence threshold, provider-time threshold, or prospective count is changed by this layer. `FULL-STACK-FORWARD-001` and `PATTERN-CONFIRM-001` remain at N=0 until genuine evidence passes the full operator gate.
