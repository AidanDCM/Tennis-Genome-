# Tennis Genome web paper validation — 2026-10-03

Settlement review: 2026-10-04 02:01–02:05 UTC (Oct. 3, 10:01–10:05 PM New York). Morning source: [immutable fixture snapshot](morning.md), captured 2026-10-03 04:06:55–04:08:45 UTC. This is an outcome-only paper reconciliation. It does not revise the morning capture or create a retrospective probability.

## Beijing ATP — five round-of-16 fixtures

Result source: [TennisDB Oct. 3 China Open results](https://tennis-db.com/matches), independently consistent with the [Beijing results listing](https://www.365scores.com/tennis/league/atp-500-beijing-232). These are public backups because an official ATP result feed for this slate was not retained. Scores are winner-first.

| Morning pair | Winner | Final score | Status |
| --- | --- | --- | --- |
| Alex de Minaur–Quentin Halys | Alex de Minaur | 3-6, 7-6(5), 7-5 | Completed per result listing |
| Alexander Zverev–Juncheng Shang | Alexander Zverev | 6-0, 6-3 | Completed per result listing |
| Andrey Rublev–Roman Safiullin | Andrey Rublev | 6-2, 3-6, 6-4 | Completed per result listing |
| Daniil Medvedev–Jan-Lennard Struff | Daniil Medvedev | 6-4, 6-3 | Completed per result listing |
| Francisco Cerundolo–Jakub Mensik | Francisco Cerundolo | 6-3, 6-3 | Completed per result listing |

## Beijing WTA — 16 round-of-64 fixtures

Result source: [official WTA Beijing 2026 match feed](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches), retrieved during this review. Raw local response: workspace `outputs/wta-beijing-matches-2026-10-03-evening.json`, SHA-256 `9b55008a0db5e1c142356d62e2e204f5732b3945cbb26ddc003a6f21f60048f2`. All matched rows are singles main-draw round 2, state `F`; winner is taken from the feed's explicit result string. Match IDs permit an identity-level join. Scores are winner-first.

| Morning pair | WTA match ID | Winner | Final score | Status |
| --- | --- | --- | --- | --- |
| Xinyu Gao–Iga Swiatek | LS047 | Iga Swiatek | 6-2, 6-3 | Final |
| Qinwen Zheng–Anna Kalinskaya | LS035 | Qinwen Zheng | 6-7(4), 6-4, 3-0 | **Retirement**; not a normally completed match |
| Elena Rybakina–Alina Charaeva | LS032 | Alina Charaeva | 3-6, 6-4, 6-3 | Final |
| Coco Gauff–Camila Osorio | LS040 | Coco Gauff | 7-6(4), 4-6, 6-2 | Final |
| Belinda Bencic–Anastasia Zakharova | LS036 | Belinda Bencic | 6-1, 7-6(3) | Final |
| Sonay Kartal–Xinyu Wang | LS033 | Sonay Kartal | 6-3, 6-2 | Final |
| Donna Vekic–Lin Zhu | LS046 | Donna Vekic | 6-1, 4-6, 6-2 | Final |
| Jelena Ostapenko–Paula Badosa | LS042 | Jelena Ostapenko | 7-6(5), 7-5 | Final |
| Kamilla Rakhimova–Leylah Fernandez | LS045 | Kamilla Rakhimova | 6-2, 4-6, 6-3 | Final |
| Xinran Sun–Cristina Bucsa | LS041 | Xinran Sun | 6-4, 7-5 | Final |
| Katie Volynets–Elise Mertens | LS043 | Elise Mertens | 6-0, 4-6, 7-5 | Final |
| Katerina Siniakova–Elina Svitolina | LS039 | Elina Svitolina | 1-6, 6-4, 6-2 | Final |
| Iva Jovic–Harriet Dart | LS044 | Iva Jovic | 2-6, 6-3, 6-3 | Final |
| Marie Bouzkova–Kimberly Birrell | LS034 | Marie Bouzkova | 6-4, 6-4 | Final |
| Ashlyn Krueger–Ann Li | LS037 | Ann Li | 6-4, 6-2 | Final |
| Maria Sakkari–Storm Hunter | LS038 | Maria Sakkari | 6-2, 6-2 | Final |

The [official WTA Swiatek report](https://www.wtatennis.com/news/4585983/by-the-numbers-six-146-and-more-from-swiateks-beijing-win) gives a 1:27 duration. The [official Charaeva report](https://www.wtatennis.com/news/4586105/charaeva-upsets-new-world-no-1-rybakina-in-beijing-second-round) gives 2:11. Durations for the other rows were not independently verified. The match feed has `MatchTimeStamp` and `LastUpdated` fields, but their semantics were not certified as actual start and finish; verified actual start/finish times remain unavailable. No walkover appears in these 16 matched feed rows; the Zheng–Kalinskaya retirement is explicit.

## Tokyo ATP — four round-of-16 fixtures

Result source: [Tennis Explorer Japan Open draw/results](https://www.tennisexplorer.com/tokyo-japan-open/2026/atp-men/?draw=1), cross-checked with [TennisDB Oct. 3 Japan Open results](https://tennis-db.com/matches). Both are public backups; an official terminal ATP result feed was not retained. Scores are winner-first.

| Morning pair | Winner | Final score | Status |
| --- | --- | --- | --- |
| Denis Shapovalov–Alejandro Tabilo | Denis Shapovalov | 7-5, 3-6, 6-4 | Completed per result listing |
| Carlos Alcaraz–Matteo Arnaldi | Carlos Alcaraz | 7-6(6), 6-1 | Completed per result listing |
| Matteo Berrettini–Adolfo Daniel Vallejo | Adolfo Daniel Vallejo | 7-6(6), 6-1 | Completed per result listing |
| Ugo Humbert–Jiri Lehecka | Jiri Lehecka | 5-7, 6-4, 6-4 | Completed per result listing |

## Forecast and evidence accounting

- Morning fixtures: **25**. Matched outcome rows: **25** (24 normal reported completions, one explicit retirement). Unresolved fixture identities: **0**. Actual start/finish time remains unverified for all 25, so none is upgraded to formal settlement evidence.
- Morning frozen-engine probabilities: **0**. Preliminary estimates: **0**. Valid probability/outcome pairs: **0**. Accuracy, Brier score, log loss, calibration residual, fair-odds outcome, and component diagnostics are **not computable**; no prediction miss can be attributed to the model.
- Formal `FULL-STACK-FORWARD-001` additions: **0**. `PATTERN-CONFIRM-001` additions: **0**. No quote-linked decisions or wagers were made.
- Operational finding: web discovery and public result reconciliation worked, but the morning capture lacked the provenance-complete chronological player state and verified pre-start timing required for the authenticated calculator. That remains the limiting step, not the probability equation.

No Sportradar credits were used for this review, and no model definition or threshold was changed.
