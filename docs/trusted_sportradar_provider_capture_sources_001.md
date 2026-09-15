# Trusted capture source identities

The promotion-capable trusted provider workflow is accepted only when the GitHub workflow run points to repository content whose capture-critical Git blob identities match `TRUSTED_CAPTURE_FROZEN_BLOBS` in `trusted_capture_provenance.py`.

The frozen set includes:

- the trusted capture workflow itself;
- `tennis_genome` and `tennis_genome.prospective` package initializers;
- the direct Sportradar HTTPS capture module;
- the provider-batch ledger implementation;
- the pagination-v2 validator;
- the anchor-packet builder;
- the census module imported by the provider-batch ledger.

All Python invocations in the trusted capture workflow use `python -S`, and the workflow does not run `pip install`. This prevents Python site initialization or repository-installed third-party packages from adding an unfrozen execution path before the capture modules load.

A later edit to any frozen capture-critical file requires a deliberate pre-result source-version change and a new set of frozen blob identities. Silent drift fails closed.
