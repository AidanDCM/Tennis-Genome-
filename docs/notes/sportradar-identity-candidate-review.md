# Review-only Sportradar player identity candidates

`scripts/report_sportradar_identity_candidates.py` reads retained season pages
and the pinned canonical pre-match Parquet locally. It makes no provider calls
and never emits an authoritative crosswalk. It retains source hashes, provider
IDs/names/country codes, candidate canonical IDs and historical IOC codes, and
explicit ambiguity dispositions. The report must be reviewed before any
candidate can enter a frozen-model history state.

For bounded capture artifact `11240861684`, the offline report found 214
distinct provider players: 150 exact normalized names with matching country
codes, 30 exact names with a documented ISO/IOC code convention, nine with
country data unavailable, two true country conflicts, one name ambiguity, and
22 unmatched. Even the 180 name-and-country-supported rows remain candidates;
name agreement alone is not a verified player identity. The two conflicts and
all unmatched/ambiguous players remain unresolved.

The generated report is a local artifact, not a repository dataset. Do not
commit provider-derived player rows or treat a report disposition as automatic
authorization to seal a crosswalk. The next gate is independent identity
evidence for each mapped player and a one-to-one check across the full covered
population, followed by duplicate reconciliation with the pinned 2026 archive.
