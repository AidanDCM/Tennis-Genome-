# Tennis Genome web paper validation — 2026-10-04

Settlement review: 2026-10-05 02:01–02:03 UTC (Oct. 4, 10:01–10:03 PM New York). The immutable [Oct. 4 morning snapshot](morning.md) listed 16 singles fixtures and no probabilities. This outcome-only record does not change it. The separate Oct. 5 pre-start snapshot is for future matches and is not settled here.

## Beijing ATP — four quarterfinals

Result source: [TennisDB Oct. 4 China Open rows](https://tennis-db.com/matches), corroborated by [BBC China Open result listings](https://bbc.com.im/sport/tennis/china-open/mens-singles/scores-and-schedule). These are public backups; a retained official ATP terminal feed was not available. Scores are winner-first.

| Morning pair | Winner | Final score | Status |
| --- | --- | --- | --- |
| Hubert Hurkacz–Karen Khachanov | Hubert Hurkacz | 7-6(2), 6-2 | Completed per result listings |
| Alex de Minaur–Andrey Rublev | Alex de Minaur | 1-6, 6-2, 6-3 | Completed per result listings |
| Alexander Zverev–Novak Djokovic | Novak Djokovic | 4-6, 6-4, 6-4 | Completed per result listings |
| Daniil Medvedev–Francisco Cerundolo | Daniil Medvedev | 7-6(4), 6-3 | Completed per result listings |

## Beijing WTA — eight round-of-32 fixtures

Result source: [official WTA Beijing 2026 match feed](https://api.wtatennis.com/tennis/tournaments/1020/2026/matches), retrieved at approximately 2026-10-05 02:01:48 UTC. Raw response retained in workspace `outputs/wta-beijing-matches-2026-10-04-evening.json`, SHA-256 `52235961d36bc275098db841779cf6feb46a841277b667b26ec2ab65c632d4e0`. These eight are main-draw singles round 3, `MatchState=F`; the feed's explicit `ResultString` establishes each winner and score. No retirement or walkover is indicated for these eight. Scores are winner-first.

| Morning pair | WTA match ID | Winner | Final score |
| --- | --- | --- | --- |
| Nikola Bartunkova–Aryna Sabalenka | LS031 | Nikola Bartunkova | 6-4, 6-3 |
| Karolina Muchova–Liudmila Samsonova | LS028 | Karolina Muchova | 4-6, 6-4, 6-2 |
| Polina Kudermetova–Mirra Andreeva | LS027 | Mirra Andreeva | 6-4, 6-1 |
| Linda Noskova–Viktorija Golubic | LS024 | Linda Noskova | 6-2, 6-1 |
| Sara Bejlek–Naomi Osaka | LS029 | Naomi Osaka | 7-6(4), 6-4 |
| Sinja Kraus–Dayana Yastremska | LS030 | Sinja Kraus | 6-1, 6-4 |
| Ekaterina Alexandrova–Diana Shnaider | LS025 | Ekaterina Alexandrova | 3-6, 6-4, 6-3 |
| Daria Snigur–Taylah Preston | LS026 | Daria Snigur | 6-1, 6-0 |

The WTA feed contains match timestamps and last-update fields, but their semantics have not been certified as actual start and finish times. They are not treated as verified start/finish evidence. Individual match durations were not independently verified.

## Tokyo ATP — four quarterfinals

Result sources: [Tennis Explorer Japan Open results](https://www.tennisexplorer.com/tokyo-japan-open/2026/atp-men/?draw=1) and [TennisDB Oct. 4 Japan Open rows](https://tennis-db.com/matches). Both are public backups; official terminal provider evidence was not retained. The [Sky Sport report](https://sport.sky.it/tennis/2026/10/04/atp-tokyo-2026-risultati-oggi-4-ottobre) independently reports Shapovalov's retirement. Scores are winner-first.

| Morning pair | Winner | Final score | Status |
| --- | --- | --- | --- |
| Jaume Munar–Kyrian Jacquet | Jaume Munar | 6-4, 6-2 | Completed per result listings |
| Carlos Alcaraz–Denis Shapovalov | Carlos Alcaraz | 7-6(3), 2-1 | **Shapovalov retired**; not a normally completed match |
| Valentin Vacherot–Arthur Fils | Valentin Vacherot | 7-5, 4-6, 6-4 | Completed per result listings |
| Jiri Lehecka–Adolfo Daniel Vallejo | Jiri Lehecka | 6-1, 6-1 | Completed per result listings |

## Forecast and evidence accounting

- The 16 morning fixture identities reconcile to 16 reported outcomes: **15 normal completions and one retirement**. No unresolved fixture remains. No verified actual-start/finish time was captured, so none is upgraded to a formal provider settlement.
- Morning frozen-engine forecasts: **0**. Preliminary estimates: **0**. Valid probability/outcome pairs: **0**. Accuracy, Brier score, log loss, calibration residual, fair-odds outcome and model-component comparisons are **not computable**. The Bartunkova upset is an outcome, not evidence that this model missed it; no prediction was made.
- Formal `FULL-STACK-FORWARD-001` additions: **0**. `PATTERN-CONFIRM-001` additions: **0**. No wagers or quote-linked decisions.
- The operational blocker remains missing legal, provenance-complete chronological player state. The New York midnight capture additionally occurred after scheduled first-court starts in Asia. The capture schedule was subsequently moved to 6 PM New York time for the following Asian day; the separate Oct. 5 snapshot reflects that timing change but does not solve the feature gap.

No Sportradar credits were used in this review. No frozen model definition or threshold was changed.
