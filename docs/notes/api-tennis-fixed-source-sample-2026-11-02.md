# Fixed source-check sample, 2026-11-02

To avoid selecting only conspicuous failures or agreements, the retained
May 3–November 1 history was sampled by a fixed identity-hash rule. The
selector verifies all ten capture receipts and raw hashes, rejects duplicate
event IDs, and admits only finished rows that parse and pass the existing
internal point-count gate. For each tour and UTC month, it takes the two
smallest `SHA256(seed|tour|event_key)` ranks, with seed
`TGE-SOURCE-CHECK-2026-11-02-v1`. It never ranks by winner, score, or point
statistics. This yielded **28 selected matches** from **3,457 internally
consistent candidates**. The local immutable sample file has SHA-256
`31fa6d8ed004bd95a8067f84b51abef50eb7420d879bee53ae5bce08eafb5d83`.
The selected IDs, source hashes, and capture run IDs remain in the local
ignored output pending source-rights review.

The first official WTA point-count comparisons are:

| Selected match | Official service points won/played | API-Tennis | Status |
| --- | --- | --- | --- |
| [Pliskova–Bouzas Maneiro, Rome](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS122) | 63/110, 50/86 | 63/110, 50/86 | Exact agreement |
| [Gauff–Sherif, Roland Garros](https://www.wtatennis.com/tournaments/903/roland-garros/2026/scores/LS71563892) | 30/54, 27/68 | 30/54, 27/68 | Exact agreement |
| [Svitolina–Lys, Berlin](https://www.wtatennis.com/tournaments/2012/berlin/2026/scores/LS014) | 41/64, 23/47 | 41/64, 23/47 | Exact agreement |
| [Krueger–Kostyuk, Wimbledon](https://www.wtatennis.com/tournaments/904/wimbledon/2026/scores/LS72320406) | 40/74, 38/58 | 40/74, 38/58 | Exact agreement |

Two other selected WTA matches from the same May–July strata (Vekic–Monnet
and Bartunkova–Tararudee) have **not** been adjudicated against exact official
point counts. The other 22 selected matches are also unreviewed. The four
agreements are a progress count, **not** a 100% source accuracy claim; pending
and unavailable official statistics must stay in the denominator of the final
review. The selected sample includes qualifying and team events, so its scope
must be reported before any claim about the frozen model's target population.

Reproduce the selection offline with
`python -m scripts.select_api_tennis_official_sample`, passing all ten
retained capture directories, a new output path, and the default seed.
The four curated official references are in
`research/source_adjudication/wta_fixed_sample_first_four.json`; the
multi-capture adjudicator verifies retained source bytes before comparing
them. Its local output has SHA-256
`3b1f1be7da23faac669d65f40ff9b733531d2d25a449144d4ac451beaaa66cb8`.
Neither script makes provider calls, updates player state, changes a frozen
forecast, or establishes an official-source license for automated reuse.

## Continuation: four more exact-count comparisons

The next checks cover two WTA and two ATP selections. Exact point totals
agree in all four:

| Selected match | Official service points won/played | API-Tennis | Source |
| --- | --- | --- | --- |
| [Kalinskaya–Shnaider, Toronto](https://nationalbankopen.com/matches-players/results/2026/kalinskaya_vs_shnaider) | 27/54, 34/55 | 27/54, 34/55 | Official tournament |
| [Bartunkova–Maria, US Open](https://www.wtatennis.com/tournaments/us-open/scores/LS73992538) | 60/91, 48/84 | 60/91, 48/84 | WTA |
| [Mochizuki–Marozsan, Montreal](https://nationalbankopen.com/matches-players/results/2026/mochizuki_vs_marozsan) | 29/56, 38/60 | 29/56, 38/60 | Official tournament |
| [Sinner–Medvedev, Rome](https://www.tennistv.com/videos/4504507/rome-2026-sf-sinner-medvedev) | 63/92, 59/104 | 63/92, 59/104 | ATP's official Tennis TV service |

The tournament source is the National Bank Open's own site; Tennis TV is
[identified by ATP as its official video service](https://www.atptour.com/apps).
These identities and point counts are corroborated, but we have **not**
established whether these sites independently collect points or share an
upstream feed with API-Tennis. The ATP Tour Stats Centre was inaccessible
(HTTP 403) to this audit. Source corroboration must not be confused with
independent measurement.

The selected-sample progress is now **8 exact agreements, 0 observed
disagreements, 20 unresolved of 28**. This is not an accuracy estimate:
the unresolved matches remain in the denominator, and examples with accessible
exact statistics may differ systematically from those without them. The
post-match point comparisons leave T0 feature chronology, canonical identity,
surface/duration, and actual-start evidence unapproved.

The Sinner–Medvedev match is also a timing warning: ATP lists a Friday May 15
semifinal [resumed on Saturday after rain](https://www.atptour.com/en/news/sinner-medvedev-rome-2026-sf-saturday),
while the retained API row carries `event_date=2026-05-16`. The comparison
reference's `event_date` binds the retained provider row; it is **not** an
officially verified actual-start date.

The additional reference files are
`research/source_adjudication/fixed_sample_next_three.json` and
`research/source_adjudication/atp_fixed_sample_sinner_medvedev.json`. Their
local adjudication outputs are bound to verified retained captures and have
SHA-256 digests
`f44f1228fe9fcbecfff56c870981c5b3b38e249b92893376f6de0d082b00835d`
and
`be419bc94d47827005145fef70b698bc7e2b45b6dae3d64decb51d8700f9fc02`.
