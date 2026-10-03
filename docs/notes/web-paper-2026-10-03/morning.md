# Tennis Genome web paper snapshot — 2026-10-03

Observed 2026-10-03 04:06:55–04:08:45 UTC (00:06:55–00:08:45 America/New_York). This snapshot describes the local Oct. 3 capture window. It is paper-only, contains no outcome information, and must not be edited after results become known.

## Retained primary sources

- [China Open official ATP/WTA order of play](https://wtafiles.wtatennis.com/pdf/draws/2026/1020/OP.pdf), released Oct. 2 at 8:53 PM Beijing time; retained as `morning-capture-2026-10-03/beijing-official-order-of-play.pdf`, SHA-256 `f937a4373c7a59315cffaf35fd427431daf01e510570030a49fb66564383a2e9`, downloaded 04:07:38 UTC. Beijing hard court; listed first-court starts at 11:00 AM Beijing time (03:00 UTC).
- [Japan Open official ATP order of play](https://japanopentennis.com/atp/application/files/7217/9092/9945/OP.pdf), released Oct. 2 at 5:27:50 PM Tokyo time; retained as `morning-capture-2026-10-03/tokyo-official-order-of-play.pdf`, SHA-256 `43e0bd10a2c2fac059c13f398f1b8b50fd5ee6d564517fb5c44e59938cd4fe65`, downloaded 04:08:38 UTC. Tokyo hard court.

The [official ATP calendar](https://www.atptour.com/en/tournaments/) identifies Beijing and Tokyo as active ATP 500 events. No sportsbook prices were used. The official PDFs are the primary fixture evidence; search-indexed third-party schedule pages were viewed only as discovery backups and were not used as a pre-start timestamp.

## Officially listed singles slate (25 matches)

Beijing ATP, round of 16 (5): Alex de Minaur–Quentin Halys; Alexander Zverev–Juncheng Shang; Andrey Rublev–Roman Safiullin; Daniil Medvedev–Jan-Lennard Struff; Francisco Cerundolo–Jakub Mensik.

Beijing WTA, round of 64 (16): Xinyu Gao–Iga Swiatek; Qinwen Zheng–Anna Kalinskaya; Elena Rybakina–Alina Charaeva; Coco Gauff–Camila Osorio; Belinda Bencic–Anastasia Zakharova; Sonay Kartal–Xinyu Wang; Donna Vekic–Lin Zhu; Jelena Ostapenko–Paula Badosa; Kamilla Rakhimova–Leylah Fernandez; Xinran Sun–Cristina Bucsa; Katie Volynets–Elise Mertens; Katerina Siniakova–Elina Svitolina; Iva Jovic–Harriet Dart; Marie Bouzkova–Kimberly Birrell; Ashlyn Krueger–Ann Li; Maria Sakkari–Storm Hunter.

The Beijing PDF has multiple courts and “followed by” slots. This text capture does not reliably associate every player pair with its individual court/time cell. **Individual scheduled start and verified actual start are unavailable in this snapshot.** The 11:00 AM Beijing first-court start equals 03:00 UTC, already past at capture; some Beijing matches were therefore already underway or completed. The remaining pairs are discovery candidates, not time-cleared pre-start predictions.

Tokyo ATP, round of 16 (4), on the Colosseum court:

| Match | Official scheduled slot (Tokyo / UTC / New York) | Status at capture |
| --- | --- | --- |
| Denis Shapovalov–Alejandro Tabilo | starts 11:00 AM / 02:00 UTC / Oct. 2 10:00 PM | excluded: scheduled start before capture |
| Carlos Alcaraz–Matteo Arnaldi | not before 12:30 PM / 03:30 UTC / Oct. 2 11:30 PM | excluded: scheduled lower bound before capture; actual start unverified |
| Matteo Berrettini–Adolfo Daniel Vallejo | not before 4:00 PM / 07:00 UTC / Oct. 3 3:00 AM | scheduled after capture; still lacks legal frozen state and verified actual-start evidence |
| Ugo Humbert–Jiri Lehecka | follows preceding match; exact start unavailable | scheduled after preceding match; still lacks legal frozen state and verified actual-start evidence |

Tokyo's court schedule may be moved by officials; scheduled slots are not verified actual starts. Other Tokyo doubles listings are outside the singles cohort.

## Frozen-input attempt and missingness

The retained official order-of-play PDFs establish fixture names, tour, tournament, round, surface and coarse schedule. They do not provide an authenticated canonical player crosswalk or the current chronological player state required by the frozen calculator: ranking/points and demographics where used, Elo and rating history, opponent-adjusted serve/return and point form, surface state, workload/rest, profile features, and provenance-complete source cutoffs. The accepted archive's 2026 extension stops in May; retained Sportradar summaries cover only a small part of the subsequent history and do not include all metadata. Filling these gaps with current post-start web stats or guessed values would contaminate the frozen prediction.

No complete legal `MatchupInput` was assembled. The production calculator was **not run**. No documented preliminary web-stat fallback method was found in the repository, so no substitute probability was invented. Sportradar calls made for this capture: **0**, because a single missing-field call would not repair the absent multi-month state or time/identity boundary.

Accounting: **25 fixtures listed; 0 frozen-engine predictions; 0 preliminary estimates; 0 formal forward-eligible records.** The evening check may reconcile results against this fixture list, but must not backfill probabilities or turn this post-start paper record into formal prospective evidence.
