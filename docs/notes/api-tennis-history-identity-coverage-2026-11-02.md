# Retained 2026 history: identity coverage before current-state replay

The offline audit verifies all ten retained API-Tennis capture receipts and raw
hashes, requires contiguous disjoint May 3–November 1 date windows, and rejects
duplicate event IDs. It reads the pinned player registry, the verified November
2 standings snapshot, and separately retained player-profile responses. No
bookmaker source, outcome, or model prediction is used to choose identities.

The retained history has **4,942 fixtures** and **994 distinct provider player
IDs**. An initial audit using the three already retained current-tournament
profile responses found 137 exact full-name/birthdate links, 687 unique
name-only proposals, and 170 unresolved or conflicting players. These are
identity evidence tiers, not source approval or a production crosswalk.

To test the lowest-cost way to improve coverage, the audit ranked unprofiled
tournaments by distinct unresolved players they might cover. Two one-call
`get_players` probes were then dispatched sequentially and retained:

| Tournament key | GitHub run | Profile rows returned | Additional exact links |
| --- | --- | ---: | ---: |
| WTA 2156 | [41520047317](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41520047317) | 240 | 170 |
| ATP 2053 | [41520229198](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41520229198) | 241 | 157 |

Both raw responses and manifests match their retained hashes and GitHub
receipts. **Two provider requests increased exact identity candidates from 137
to 464.** The remaining player tiers are 360 unique name-only proposals, 64
names absent from the pinned registry, 48 without a current full name, six
ambiguous name-only proposals, three ambiguous profile matches, seven
incomplete profiles, and 42 profile/registry mismatches. The audit explicitly
does not replace a conflicting profile name or birthdate with a standings name.
Repeated profile responses may have different season aggregates; only full
name and birthdate are compared for identity consistency.

Among the 3,457 point-consistent finished matches, 530 had both players at the
exact tier before the two probes and **2,400 after them**. Another 518 have two
proposed identities with at least one name-only link, and 539 remain unresolved.
This is identity coverage only; none of the 2,400 matches is thereby admitted
as a trustworthy source of point counts. The newer local report also records
a greedy next-call plan. That plan is an **upper bound**:
`get_players` may return fewer of those players, and exact name/birthdate
matching can still fail. It is not a reason to spend more calls without a
current-state admission policy.

Raw provider responses and match-level identity proposals remain local in
`outputs/api-tennis-history-identity-audit-2026-11-02-after-two-probes.json`.
The reusable audit is `scripts/audit_api_tennis_history_identity.py`. No
API-Tennis history row was admitted to the frozen model, no prospective
prediction was backfilled, and the model definition did not change.

Next, define and test the source-admission rule for outcomes versus point
statistics, resolve identity exceptions and tournament surface for the subset
needed by current targets, then reconcile overlap with the pinned 2026 archive.
Only after that should the existing chronological feature builders receive a
candidate current-history stream.
