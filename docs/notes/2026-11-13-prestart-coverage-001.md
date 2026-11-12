# November 13 UTC pre-start capture coverage

Captured on November 12 at 16:34:17 UTC, before both provider-listed starts. The one-call [API-Tennis Daily Fixture Inventory run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43259990606) retained artifact `13963092267`. The downloaded manifest, raw fixtures, and filtered singles matched the retained receipt hashes. The raw SHA-256 is `71ec2171018e694879d49a0d1b0712b89fb941ea7e945ad547cec3ebfaf3109a`; the filtered singles SHA-256 is `9ac3147e5a2c241148779b5749ddfa4eed244cf8a460b2fa7eb9b60ea1d6cb41`. This is a source snapshot, not a forecast.

| Measure | Count |
| --- | ---: |
| ATP/WTA singles in the next-UTC-date provider inventory | 2 |
| Supported with complete legal calculator state | 0 |
| New pre-match probabilities made | 0 |
| New pre-match probabilities frozen | 0 |
| Scheduled matches skipped | 2 |
| Authenticated full-stack forecasts | 0 |

The provider lists Mirra Andreeva–Karolina Muchova (event `12177325`, 20:00 UTC) and Aryna Sabalenka–Elina Svitolina (event `12177331`, 21:30 UTC) under **“Finals - Riyadh”**. The [official WTA tournament schedule](https://www.wtatennis.com/tournaments/wta-finals/match-schedule) places November 13 round-robin play at **Indian Wells, California**, and the [official event page](https://www.wtatennis.com/tournaments/808/fage-wta-finals-indian-wells/2026) identifies the surface as hard. The provider event location is materially inconsistent with the tour source. The listed starts are provider scheduled times, not verified actual starts.

Neither fixture has a qualified current-player-state route into the authenticated frozen calculator. The existing WTA Web Shadow intake does not support this Finals round-robin format. Both matches were excluded before calculation. No probability was invented or backfilled, and this inventory does not enter formal FULL-STACK-FORWARD evidence. The unresolved work is event identity reconciliation and chronological current-player-state qualification.
