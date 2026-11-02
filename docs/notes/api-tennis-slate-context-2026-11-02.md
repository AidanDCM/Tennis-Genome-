# November 3 API-Tennis slate context check

The retained one-call November 3 UTC fixture inventory lists 36 ATP/WTA singles
fixtures: 11 ATP Paris, 8 WTA Hong Kong, and 17 WTA Chennai. Its GitHub run is
[41492934956](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41492934956).
This is a scheduled fixture inventory, not a prediction slate.

On November 2, the trial workflows retained one current ATP/WTA standings
snapshot (two provider calls) and one draw and one player-profile response for
each of those three tournaments (six calls). The successful workflow runs were
[standings 41513797254](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41513797254),
[Paris draw 41513782406](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41513782406),
[Paris players 41514031375](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41514031375),
[Hong Kong draw 41513946485](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41513946485),
[Hong Kong players 41514115221](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41514115221),
[Chennai draw 41513792448](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41513792448),
and [Chennai players 41514295916](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41514295916).
One Hong Kong draw dispatch was canceled while pending by GitHub concurrency;
it ran no job and made no provider request. Its sequential replacement succeeded.

The offline context audit verifies retained raw hashes against manifests and
manifests against GitHub receipts. Of 36 fixtures, tournament surface was present
for 36, both players had current standings for 35, both had birthdates for 35,
and 33 had the same player IDs in fixture and draw. The three exceptions are all
Chennai:

At capture, 33 fixture statuses were `1`, two were `Set 1`, and one was
`Cancelled`. The two `Set 1` rows need independent timing review; the fixture
date alone cannot establish that they had not begun.

| Fixture event key | Players | Finding |
| --- | --- | --- |
| 12176133 | J. Teichmann / J. Garland | Fixture identifies Teichmann as 33667; draw uses 2077. Current standings and birthdate are also missing for fixture ID 33667. |
| 12176135 | M. Uchijima / R. Sramkova | Fixture identifies Uchijima as 460; draw uses 101757. |
| 12176405 | E. Jacquemot / L. Stefanini | Fixture is canceled and has no matching draw event key. |

The two ID conflicts must not be resolved by matching names alone. The current
standings are a November 2 snapshot, not historical ranks. The responses do not
establish verified actual start, historical match duration, height, or handedness.
The canonical schema permits several of those fields to remain unknown; their
absence is a feature-quality limitation rather than necessarily a parser error.

No retained API-Tennis history has yet been admitted wholesale into the frozen
production state. The existing [point-consistency audit](api-tennis-point-consistency-2026-11-02.md)
found 992 conflicting point-stat records, and source/context qualification and
chronological state construction remain. **This context check produced zero
authenticated frozen-engine predictions and zero formal forward observations.**
The reusable offline audit is `scripts/audit_api_tennis_slate_context.py`; raw
provider responses and the match-level JSON report stay in local `outputs/`.
