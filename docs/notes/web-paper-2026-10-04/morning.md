# Tennis Genome web paper snapshot — 2026-10-04

Observed 2026-10-04 04:07–04:09 UTC (00:07–00:09 New York). This is the immutable morning schedule/input assessment. It contains no Oct. 4 outcome information and must not be edited after results become known.

## Primary fixture evidence

- [Official China Open ATP/WTA order of play](https://wtafiles.wtatennis.com/pdf/draws/2026/1020/OP.pdf), for Sunday Oct. 4, released Oct. 3 at 8:40 PM Beijing time. Retained at workspace `outputs/morning-capture-2026-10-04/beijing-official-order-of-play.pdf`, SHA-256 `fafb568c0bc00f59549f7dec50afee35ccc6dda13c44b931508089f0642a8821` (downloaded about 04:07:41 UTC). Hard court. First courts begin 11:00 AM Beijing time = 03:00 UTC, **over an hour before this capture**. Individual court slots below were read from the rendered PDF grid; “followed by” is not an exact start time.
- [Official Japan Open ATP order of play](https://japanopentennis.com/atp/application/files/9917/9101/1273/OP.pdf), for Sunday Oct. 4, released Oct. 3 at 3:58:39 PM Tokyo time. Retained at workspace `outputs/morning-capture-2026-10-04/tokyo-official-order-of-play.pdf`, SHA-256 `90ea251d9ddff50c63c2f49765ee6ce562a515e78b7542ba65788fdf5baf65c0` (downloaded about 04:07:43 UTC). Hard court. First singles court began 11:00 AM Tokyo time = 02:00 UTC, **over two hours before this capture**. Matches may be moved.

No sportsbook information or Oct. 4 results were consulted for this prediction capture. The prior day's [outcome-only reconciliation](../web-paper-2026-10-03/evening.md) resolves stale “or” opponents in the already-released official orders of play; this is legitimate pre-Oct. 4 information, not an Oct. 4 outcome.

## Officially listed singles slate — 16 fixtures

Beijing ATP quarterfinals (4): Hubert Hurkacz–Karen Khachanov (Diamond, not before 1 PM / 05:00 UTC); Alex de Minaur–Andrey Rublev (Diamond, followed by Hurkacz–Khachanov); Alexander Zverev–Novak Djokovic (Diamond, not before 7 PM / 11:00 UTC); Daniil Medvedev–Francisco Cerundolo (Lotus, not before 4:30 PM / 08:30 UTC). The official PDF still says “F. Cerundolo OR J. Mensik” in the last match; the previously retained Oct. 3 result resolves that opponent as Cerundolo. **Actual starts are unverified for all four.** The listed “not before” slots are future lower bounds at capture but are not independently verified actual-start evidence.

Beijing WTA round of 32 (8): Nikola Bartunkova–Aryna Sabalenka (Diamond, starts 11 AM / 03:00 UTC); Karolina Muchova–Liudmila Samsonova (Diamond, not before 8:30 PM / 12:30 UTC); Polina Kudermetova–Mirra Andreeva (Lotus, not before 1 PM / 05:00 UTC); Linda Noskova–Viktorija Golubic (Lotus, follows the prior match); Sara Bejlek–Naomi Osaka (Lotus, not before 7 PM / 11:00 UTC); Sinja Kraus–Dayana Yastremska (HSBC Moon, starts 11 AM / 03:00 UTC); Ekaterina Alexandrova–Diana Shnaider (HSBC Moon, follows the prior match); Daria Snigur–Taylah Preston (HSBC Moon, follows the Alexandrova match). **Actual starts are unverified for all eight.** Bartunkova–Sabalenka and Kraus–Yastremska had scheduled starts before capture and are excluded from pre-start prediction. The other “followed by” matches require actual-start checks.

Tokyo ATP quarterfinals (4):

| Pair | Official scheduled slot in Tokyo | UTC lower bound | Status at capture |
| --- | --- | --- | --- |
| Jaume Munar–Kyrian Jacquet | Colosseum, starts 11:00 AM | 02:00 | Scheduled start before capture; excluded from pre-start prediction |
| Carlos Alcaraz–Denis Shapovalov | Colosseum, not before 1:00 PM | 04:00 | Lower bound before capture; actual start unverified |
| Valentin Vacherot–Arthur Fils | Colosseum, not before 4:00 PM | 07:00 | Future lower bound, but legal frozen player state unavailable |
| Jiri Lehecka–Adolfo Daniel Vallejo | Following on show court | Exact time unavailable | Legal frozen player state and actual start unavailable |

The official Tokyo PDF still lists Humbert or Lehecka versus Berrettini or Vallejo. The [Oct. 3 retained paper result](../web-paper-2026-10-03/evening.md) resolves Lehecka and Vallejo before today's play. The Tokyo PDF's text layout does not certify an exact individual scheduled time for the final quarterfinal.

## Frozen input and source assessment

The official PDFs establish event, tour, round, surface, names and coarse scheduling. They do **not** establish authenticated canonical player IDs and complete chronological player state for the frozen calculator: as-of rankings/points and demographics where used, Elo/rating history, opponent-adjusted serve/return and point form, surface state, workload/rest and recent durations, profile inputs, relevant source cutoffs, and the full verified production artifacts. The accepted 2026 historical extension still stops in May, leaving months of unsourced state for this slate. Retained Sportradar history is insufficient to fill that gap. A limited live API call would not repair the multi-month missing state; **zero Sportradar calls** were made. No documented preliminary web-stat fallback has been established in the repository, so no substitute probability was generated.

Accounting: **16 fixtures listed; 0 authenticated frozen predictions; 0 preliminary estimates; 0 formal forward-eligible predictions.** Scheduled times are not verified actual starts. No post-start statistics, guessed player values, quote information or match outcomes were used in a probability. The main operational blocker remains the missing legal as-of feature pipeline; additionally, a single New York midnight capture occurs after the start of Asian daytime sessions. This schedule cannot, by itself, deliver comprehensive pre-start coverage for Beijing or Tokyo.
