# November 8 UTC pre-start capture coverage

Observed November 7 before the scheduled matches. Source is the one-call
[API-Tennis Daily Fixture Inventory run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42423028092),
artifact `13593759986`. The raw fixture SHA-256 is
`2b03c59a4c10036028890be6ccc4cafe12595777c4616b98fffcc393d3067a3e`;
the filtered ATP/WTA singles SHA-256 is
`d0fe1bbbc5fb0758b5d301ef25df95b4acfa751820dcd4ed0ac00e33282f8a0a`.
The downloaded files match both hashes, and the manifest SHA-256 matches the retained
GitHub receipt. This is a schedule inventory, not a source of model probabilities.

| Measure | Count |
| --- | ---: |
| ATP/WTA singles rows in next-UTC-date inventory | 12 |
| Canceled rows | 1 |
| Noncanceled scheduled rows | 11 |
| Supported WTA Web Shadow targets | 2 |
| Paper forecasts made and frozen before scheduled start | 2 |
| Noncanceled rows without a forecast | 9 |
| Authenticated formal full-stack forecasts | 0 |

The two frozen paper forecasts are Hong Kong final Claire Liu–Alexandra Eala,
[PR #416](https://github.com/AidanDCM/Tennis-Genome-/pull/416), and Chennai final
Magda Linette–Janice Tjen, [PR #422](https://github.com/AidanDCM/Tennis-Genome-/pull/422).
Both use pinned player history through June 2 and have `production_eligible=false`.
The Chennai slate run `42418376306` and bound artifact `13592139271` were independently
verified; PR #422's exact head passed manually dispatched CI before merge, because a
bot-authored pull request did not start its own check. Merged-main CI passed.

The nine noncanceled unforecast rows are seven ATP fixtures (six Stockholm fixtures
and the Paris final) and two WTA Riyadh Finals fixtures. The ATP production route
lacks qualified current player state and complete authenticated inputs; the WTA Web
Shadow intake configuration does not include Riyadh and its round-robin/event context
has not been qualified. The additional Riyadh Rybakina–Noskova row is explicitly
canceled and excluded. The provider's scheduled status and time still need official
cross-check before any unmatched fixture could be treated as a prediction target.

No missing forecast may be backfilled after start. This coverage gap is an operational
and source-qualification finding, not a scored model miss. The upcoming result
settlement must keep the two Web Shadow forecasts, the Hong Kong simple-logit
research challenger pair, and any formal full-stack observations in separate cohorts.
