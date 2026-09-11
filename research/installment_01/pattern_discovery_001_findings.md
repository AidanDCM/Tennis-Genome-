# PATTERN-DISCOVERY-001 Findings

Status: **EXPLORATORY DISCOVERY COMPLETE — NOT INDEPENDENT CONFIRMATION**

## Immutable execution

The first preregistered residual-pattern search ran once on:

- discovery code/workflow SHA: `6014a691fb53cd7f3dbdd6179ac20419b80002f4`
- workflow run: `34633660089`
- Actions artifact ID: `10277681971`
- Actions artifact ZIP SHA-256: `fbfabc13d28d6fb0b04d1c8642b812d01b8c149f429a782d04009909f1042b29`
- PATTERN-DISCOVERY artifact SHA-256: `6a867c4b4cf236567a10a4567a209fdbbf397da201147f3a8537e71de4675399`
- residual ledger SHA-256: `3fb6ae9b670dca30e2b5085c0ace72ced926be16e1d8bbfa9874b0c7abcb0c6c`
- feature ledger SHA-256: `1d71222ab477eec65a06a3e7c76ac0af1c282e6f2a7164e8c47b37afc7192628`

Every frozen source hash was verified before the search. Candidate definitions and cut points were learned from years through 2022 only; 2023-2025 were used only as the preregistered internal-validation block.

## Search accounting

The v1 search generated **425 total candidates**.

| Tour | Family | Generated | Survivors |
|---|---|---:|---:|
| ATP | single_variable | 118 | 1 |
| ATP | pairwise_context | 51 | 1 |
| ATP | uncertainty_ood | 43 | 2 |
| WTA | single_variable | 119 | 0 |
| WTA | pairwise_context | 51 | 0 |
| WTA | uncertainty_ood | 43 | 0 |

Total survivors: **4**, all ATP.

These are exploratory candidate hypotheses only. None is production-eligible or independently confirmed.

## Survivor 1 — ATP lowest Profile Gap quintile

Candidate ID: `ATP:single_variable:0914faa2399d38c4`

Definition after Amendment 002 range completion:

- feature: `profile_gap`
- first discovery-fitted quintile
- operational future rule: `profile_gap < -0.4045998117259577`

Discovery block:

- N = `3,060`
- mean Market+Core residual = `-0.031143878674067826`
- raw p = `6.933939247755703e-05`
- BH-adjusted p = `0.008182048312351729`
- 95% bootstrap interval = `[-0.04680817602594602, -0.015547947077366378]`

Internal validation 2023-2025:

- N = `1,248`
- mean residual = `-0.03269372391111453`
- 95% bootstrap interval = `[-0.05681102102883317, -0.008650407417183465]`
- annual residual sums:
  - 2023: `-10.943243477273016`
  - 2024: `-14.914021177428523`
  - 2025: `-14.9445027863694`
- concentration ratio = `0.3662709662750126`

Frozen discovery correction diagnostic (`p_market_core - 0.031143878674067826` within the cell):

- baseline Brier = `0.18994968761918674`
- corrected Brier = `0.18888314486756072`
- Brier improvement = `0.001066542751626015`
- baseline log loss = `0.5564273218944269`
- corrected log loss = `0.5538036906840861`
- log-loss improvement = `0.0026236312103408155`

Interpretation: in this historical regime, the frozen Market+Strict-Core probability overpredicted Player A by roughly 3.1-3.3 percentage points on average. This is the strongest v1 discovery survivor, but still requires a new untouched future sample.

## Survivor 2 — ATP largest absolute Profile Gap quintile

Candidate ID: `ATP:uncertainty_ood:90451092e0e9a458`

Definition after Amendment 002 range completion:

- feature: `abs_profile_gap`
- fifth discovery-fitted quintile
- operational future rule: `abs(profile_gap) >= 0.47108555150900466`

Discovery block:

- N = `3,060`
- mean residual = `-0.022734415112664306`
- raw p = `0.0030689004780850015`
- BH-adjusted p = `0.06598136027882753`
- 95% bootstrap interval = `[-0.03802092105747449, -0.008085569564439643]`

Internal validation 2023-2025:

- N = `1,325`
- mean residual = `-0.023225072947050746`
- 95% bootstrap interval = `[-0.04493696598158437, -0.0009699301362726131]`
- annual residual sums:
  - 2023: `-5.600186388392501`
  - 2024: `-13.364341977620612`
  - 2025: `-11.80869328882913`
- concentration ratio = `0.43428478589331254`

Frozen discovery correction diagnostic (`p_market_core - 0.022734415112664306` within the cell):

- baseline Brier = `0.17291035269625976`
- corrected Brier = `0.17237113595990705`
- Brier improvement = `0.0005392167363527101`
- baseline log loss = `0.5154259166601437`
- corrected log loss = `0.5131726792578928`
- log-loss improvement = `0.0022532374022509183`

Interpretation: large absolute Profile Gap states also showed a repeated negative Market+Core residual. This survivor is weaker than Survivor 1 but retained direction, a below-zero validation interval, and improved both proper scores under the frozen correction.

## Survivor 3 — ATP low Profile Gap on clay

Candidate ID: `ATP:pairwise_context:024ccacb399b35e9`

Definition:

- surface = `Clay`
- first discovery-fitted Profile Gap tertile
- operational future rule: `surface == Clay` and `profile_gap < -0.25847459234483483`

Discovery:

- N = `1,519`
- mean residual = `-0.038016749298630845`
- raw p = `0.0008624958767658538`
- BH-adjusted p = `0.043987289715058546`
- bootstrap interval = `[-0.06138566307440142, -0.015857203513580057]`

Validation:

- N = `622`
- mean residual = `-0.01930066799562021`
- bootstrap interval = `[-0.055382210569089096, 0.01758412064478086]`
- annual sums: 2023 `-8.174451716459098`, 2024 `2.2350722706024113`, 2025 `-6.065636047419083`
- concentration ratio = `0.4961682738954233`
- frozen correction improved Brier only by `0.000022226486918824895` and worsened log loss by `0.0012769427802409306`

This survives the original rule but is materially weaker: the validation interval crosses zero, one validation year reverses direction, the concentration gate is only narrowly satisfied, and log loss worsens under the frozen correction.

## Survivor 4 — ATP high absolute Profile Gap with low absolute Genome signal

Candidate ID: `ATP:uncertainty_ood:fcc0038894ce357e`

Definition after Amendment 002 range completion:

- `abs_profile_gap >= 0.34720321530770193` (top tertile)
- `abs_genome_signal < 0.02140617852518821` (bottom tertile)

Discovery:

- N = `1,712`
- mean residual = `-0.03451877877835203`
- raw p = `0.0010205767739229015`
- BH-adjusted p = `0.043884801278684764`
- bootstrap interval = `[-0.0550712543482269, -0.014984344854731074]`

Validation:

- N = `756`
- mean residual = `-0.007867373549838444`
- bootstrap interval = `[-0.03922749414992089, 0.022876831704983832]`
- annual sums: 2023 `-5.3181310039029555`, 2024 `8.08839007520202`, 2025 `-8.717993474976927`
- concentration ratio = `0.39404224909280483`
- the frozen correction worsened Brier by `0.0006463059697525142` and worsened log loss by `0.0006176792156749045`

This survives the original rule but is materially weaker than Survivors 1-2: the validation interval crosses zero, one year reverses direction, and both proper-score diagnostics worsen.

## Outcome of discovery v1

The strongest reproducible signal from PATTERN-DISCOVERY-001 is therefore not a new broad Genome effect. It is a **Profile-Gap regime effect in ATP**, particularly the most negative signed Profile Gap states and, more generally, very large absolute Profile Gap states.

This does not overturn the failed broad confirmatory family. The broad Profile Gap claim remains failed. The v1 result instead generates narrower future hypotheses about specific ATP Profile Gap regimes.

All four original survivors remain in the immutable discovery record. For practical independent confirmation, the next protocol may prioritize Survivors 1 and 2 because they are the two survivors that additionally satisfy all of the following observed validation diagnostics:

- 2023-2025 bootstrap interval excludes zero in the discovery direction;
- all three annual residual sums have the same sign;
- the frozen discovery correction improves both Brier score and log loss.

That prioritization is explicitly a **post-discovery hypothesis-selection step**, not additional evidence. Its validity must come entirely from a new untouched future sample.
