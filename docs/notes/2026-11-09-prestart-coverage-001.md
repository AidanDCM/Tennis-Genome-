# November 9 UTC pre-start capture coverage

Observed November 8 before all six listed starts. The one-call
[API-Tennis Daily Fixture Inventory run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42532889586)
retained artifact `13638396452` at `2026-11-08T22:59:38Z`. Its receipt reports
one provider request, raw SHA-256
`4e68a0a7c01dc65071ae2ece7ef951caf3d3e57e1953af4908e91fee7d60b9d6`,
and filtered singles SHA-256
`8a2afa9cc71089c0df58221ce1d7ca96667a807a3686a9d9949e967425f66d5e`.
The downloaded raw, filtered, and manifest files match the receipt hashes.
This is a source snapshot, not a model forecast.

| Measure | Count |
| --- | ---: |
| ATP/WTA singles scheduled in the next-UTC-date inventory | 6 |
| Supported with complete legal calculator state | 0 |
| New pre-match probabilities made | 0 |
| New pre-match probabilities frozen | 0 |
| Scheduled matches skipped | 6 |
| Authenticated full-stack forecasts | 0 |

Four ATP Stockholm singles fixtures are listed: Duckworth–Norrie,
Etcheverry–Dahlin, Michelsen–Hanfmann, and Vallejo–Humbert. The
[ATP tournament page](https://www.atptour.com/en/tournaments/stockholm/429/overview)
supports the event, dates, and hard surface; individual pairings and starts
remain provider-only in this snapshot. The frozen full-stack calculator lacks
qualified current player state, and there is no supported ATP Web Shadow
route. None was assigned a probability.

The provider lists Sabalenka–Muchova and Andreeva–Svitolina as **"Finals -
Riyadh"**. The [official WTA tournament page](https://www.wtatennis.com/tournaments/808/wta-finals-indian-wells/2026)
and [November 9 order of play](https://www.wtatennis.com/news/4606429/wta-finals-2026-day-2-preview-can-aryna-sabalenka-even-series-with-karolina-muchova)
instead place these exact matchups at the **WTA Finals in Indian Wells,
California**, on outdoor hard courts. This is a material event-location and
context conflict, not a harmless label variation. The existing WTA Web Shadow
intake returned no eligible unseen targets and does not qualify this Finals
format; neither match was sent through a calculator. No provider metadata
probe was justified while the event identity conflicted with the tour.

Zero predictions here are a coverage failure, not six model losses. No
probabilities may be backfilled after start, and this inventory does not enter
formal FULL-STACK-FORWARD evidence. The next operational priority is a
qualified chronological current-player-state route plus explicit event
identity reconciliation before model input construction.
