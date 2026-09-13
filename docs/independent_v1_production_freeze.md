# TGE-Independent-v1 Production Freeze

Status: **sealed production-development artifact from the accepted 2000–2025 research source**.

This document records the exact immutable evidence produced by the successful production-freeze workflow. It does not alter the frozen probability architecture, promote a hard PASS policy, or change `PATTERN-CONFIRM-001`.

## Freeze provenance

- Workflow: `Freeze TGE-Independent-v1 Production Bundle`
- Workflow run: `34770189943`
- Workflow conclusion: `success`
- Seal commit: `ff44fc5c98216463ea948416e6b01445ac064e36`
- Source repository: `Aneeshers/tennis-sackmann-archive`
- Source commit: `83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Development coverage: `2000–2025`
- Source permission status used by the canonical builder: `research_allowed`
- Source license: `CC BY-NC-SA 4.0`

The spent partial-2026 holdout is not part of this terminal fit.

## Sealed artifact fingerprints

- Production bundle SHA-256: `7a5874325d57d4fa670e5515607a2ec6a02ecedc9fdfb87338367e8e4556a2f1`
- ATP neighbor-bank SHA-256: `9ff8e6e728342f73f6863c4ccc56550ba66e1583d5a250636d9cc32b13c37862`
- WTA neighbor-bank SHA-256: `5faef42f9809c576954b15786f6f65e542873f1e3618eb7c7333a8dba999a9e9`
- GitHub Actions evidence ZIP SHA-256: `9bd71729d98d69f1a4adfd1c61b589ea06312ee26dfb84ea93b7a8babf75ece7`
- GitHub Actions artifact ID: `10322467009`

The production bundle's self-hash transitively records the frozen model mappings and the neighbor-bank digests.

## Production populations

### ATP

- Eligible terminal Core training rows: `75,112`
- Historical-alignment meta rows: `68,518`
- Conditioned-unfamiliarity training rows: `68,518`
- Frozen neighbor-bank rows: `71,832`
- Neighbor representation: `full_genome`
- Primary k: `100`
- Candidate limit: `1000`
- Canonical-content SHA-256: `00cef02ed493fbb7338415365648a3150b8c71953609013ab6759e57154b04ff`

### WTA

- Eligible terminal Core training rows: `69,105`
- Historical-alignment meta rows: `63,201`
- PointSim conditional-meta rows: `60,129`
- Frozen neighbor-bank rows: `66,224`
- Neighbor representation: `strict_core_geometry`
- Primary k: `100`
- Candidate limit: `1000`
- Canonical-content SHA-256: `4bb0803a6324d0229a949ca29aeb31720beb693f854044bdc704202a5e593124`

The WTA bundle also contains the frozen Elo-only and A+B disagreement diagnostics. The ATP bundle contains the frozen conditioned-unfamiliarity diagnostic.

## Verification gates completed

The successful workflow completed all of the following before the seal commit was pushed:

1. normalized and re-linted the production freezer source;
2. asserted the development-only 2000–2025 boundary;
3. downloaded exactly 52 pinned ATP/WTA source files;
4. rebuilt canonical ATP and WTA datasets;
5. required the exact accepted canonical content hashes;
6. fit and wrote the terminal production bundle and deterministic gzip neighbor banks;
7. reloaded the bundle with bank-digest verification;
8. asserted the frozen 2025 cutoff, k=100 banks, ATP unfamiliarity artifact, WTA PointSim artifact, and WTA disagreement artifacts;
9. passed the focused production/independent/neighbor boundary suite: `27 passed`;
10. committed the normalized production source and sealed artifacts to the production-freeze branch;
11. uploaded the three-file evidence artifact.

## Scientific boundary

This freeze means there is now a reproducible terminal `TGE-Independent-v1` artifact for post-development inference. It does **not** mean:

- future match outcomes are known;
- a hard PASS/PREDICT policy exists;
- the model has proven sportsbook edge or profitability;
- historical 2000–2025 matches may be replayed using this terminal fit without leakage;
- `PATTERN-CONFIRM-001` may accumulate N without its separately frozen live-provider gates.

`PATTERN-CONFIRM-001` remains separate and at N=0 until its own prospective intake contract can be satisfied.
