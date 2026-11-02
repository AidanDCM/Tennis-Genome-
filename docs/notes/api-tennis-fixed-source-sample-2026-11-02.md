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
