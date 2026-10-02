# ATP identity corroboration from retained match overlap

`scripts/corroborate_sportradar_overlap_identities.py` uses the eight retained
2026 ATP tournament feeds that overlap the pinned 2026 match CSV. It requires
the already-reviewed tournament map in
`sportradar-2026-overlap-season-map.json` and performs no provider requests.
It joins complete player pairs, requires the same winner, rejects repeated
pair and ID conflicts, and records event IDs plus hashes of every source page.
The report explicitly says `authoritative_crosswalk: false` and must not be
fed directly to the prospective predictor.

The 2026-10-02 offline run matched 323 events and corroborated 155 player ID
pairs. All 74 IDs also appearing in the newer six-season identity candidate
report agreed with its unique canonical candidate. This is useful independent
match-level corroboration of candidate identities. It cannot establish the
identity of a player absent from the overlap, resolve future renames or source
errors, or replace human/source review for an authoritative crosswalk.

Reproduce with retained data (set `PYTHONPATH=src`):

```text
python scripts/corroborate_sportradar_overlap_identities.py \
  --capture-root <retained-census>/season-summaries-census/seasons \
  --canonical-csv data/independent_freeze_processed/atp/atp_matches_2026.csv \
  --season-map docs/notes/sportradar-2026-overlap-season-map.json \
  --output <new-output-file>.json
```

The local run report is retained as
`outputs/sportradar-atp-overlap-identity-corroboration-v2-2026-10-02.json` in the
task workspace. This does not produce a pre-start prediction or increment a
registered prospective cohort.
