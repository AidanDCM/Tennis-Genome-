# Tennis Genome web paper snapshot — 2026-10-05

Captured 2026-10-04 22:00:57–22:02 UTC (6:00:57–6:02 PM New York) for the following Asian tournament day. This is a pre-outcome schedule/input record. Do not edit it after the Oct. 5 results become known.

## Retained official sources

- [China Open ATP/WTA revised order of play](https://wtafiles.wtatennis.com/pdf/draws/2026/1020/OP.pdf), Monday Oct. 5, released Oct. 5 at 12:41 AM Beijing time; retained at workspace `outputs/morning-capture-2026-10-05/beijing-official-order-of-play.pdf`, SHA-256 `68da3d3e7fa04962a807aa7f97e82390f3f215a931c66d2682611770b240259f`, downloaded about 22:01:18 UTC. First singles start 11 AM Beijing = 03:00 UTC Oct. 5, roughly five hours after capture. Hard court. Individual slots below were checked against the rendered PDF grid.
- [Japan Open ATP order of play](https://japanopentennis.com/atp/application/files/8417/9111/4774/OP.pdf), Monday Oct. 5, released Oct. 4 at 7:51:20 PM Tokyo time; retained at workspace `outputs/morning-capture-2026-10-05/tokyo-official-order-of-play.pdf`, SHA-256 `7350e89639fdf23727a303e0763b80e8d1c58f2a600411da13928b825f3d2f2c`, downloaded about 22:01:20 UTC. First singles not before 4 PM Tokyo = 07:00 UTC Oct. 5, roughly nine hours after capture. Hard court. Matches can be moved by officials.

No Oct. 5 result or sportsbook quote was consulted in this snapshot. Both official orders are pre-start schedule evidence, not verification of actual start times.

## Beijing singles — ten fixtures

| Tour / round | Pair | Official court and local slot | UTC lower bound |
| --- | --- | --- | --- |
| WTA R32 | Donna Vekic–Iga Swiatek | Diamond, starts 11 AM | 03:00 |
| WTA R32 | Marie Bouzkova–Qinwen Zheng | Diamond, follows Vekic–Swiatek | Unspecified |
| ATP SF | Alex de Minaur–Hubert Hurkacz | Diamond, not before 3 PM | 07:00 |
| ATP SF | Novak Djokovic–Daniil Medvedev | Diamond, not before 7 PM | 11:00 |
| WTA R32 | Coco Gauff–Xinran Sun | Diamond, not before 8:30 PM | 12:30 |
| WTA R32 | Iva Jovic–Kamilla Rakhimova | Lotus, follows opening doubles | Unspecified |
| WTA R32 | Belinda Bencic–Ann Li | Lotus, not before 3 PM | 07:00 |
| WTA R32 | Maria Sakkari–Elina Svitolina | Lotus, follows Bencic–Li | Unspecified |
| WTA R32 | Alina Charaeva–Sonay Kartal | HSBC Moon, follows opening doubles and another doubles match | Unspecified |
| WTA R32 | Jelena Ostapenko–Elise Mertens | HSBC Moon, not before 4:30 PM | 08:30 |

Tokyo ATP semifinals (two): Carlos Alcaraz–Jaume Munar, Colosseum **not before 4 PM Tokyo / 07:00 UTC**; Jiri Lehecka–Valentin Vacherot, Colosseum **not before 6 PM Tokyo / 09:00 UTC**. Doubles are outside the singles cohort.

The slate contains **12 singles fixtures: ten Beijing and two Tokyo**. All official lower bounds that have explicit times are later than capture. “Followed by” has no certified individual start time; future order-of-play publication alone does not establish verified actual start. Canonical player and event IDs would still need to be resolved and authenticated before any formal forecast.

## Frozen-feature attempt and accounting

The PDFs supply legitimate opponent names, tours, rounds, surface, venue and scheduled slots. They do not supply the complete as-of player state required by the frozen calculator: canonical IDs; valid rankings/points and demographics where used; rating/Elo history; opponent-adjusted serve, return and point form; surface-specific history; rest/workload and recent match duration; profile features; source cutoffs and provenance. The accepted 2026 historical extension stops in May, and retained Sportradar history does not fill the intervening months for these players. No single live Sportradar request can repair the multi-month gap. **Sportradar calls used: 0.** No documented preliminary web-stat fallback exists in the repository.

**12 fixtures listed; 0 complete legal `MatchupInput` objects; 0 frozen-engine probabilities; 0 preliminary estimates; 0 formal prospective-eligible records.** No post-start inputs, guessed values, outcomes, bookmaker prices, or substitute equations were used. This earlier capture fixes the previous Asia-session timing failure, but the chronological feature acquisition gap still prevents a defensible model calculation.
