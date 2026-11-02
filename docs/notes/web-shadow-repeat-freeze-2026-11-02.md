# November 3 Web Shadow repeat-freeze repair

The first November 3 WTA Web Shadow run, GitHub Actions
[41494524336](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41494524336),
was frozen in merged PR #364. The scorecard contains seven immutable
pre-start, paper-only predictions. The next intake added Selekhmeteva–Kostovic,
but its [slate run 41495754169](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41495754169)
again predicted the **same seven** matches and skipped the added fixture.
The [automatic freeze 41495992480](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/41495992480)
failed because those seven match IDs were already in the scorecard. The
scorecard's unique-match guard correctly protected the original predictions.

The auto-freeze workflow now classifies the GitHub-digest-verified bound
artifact before mutation. A fully repeated prediction set is skipped with a
run summary; a fully new set follows the existing transactional freeze path;
a mixture of old and new IDs fails for explicit operator review. The precheck
binds the artifact manifest to the triggering workflow run and source commit.
It does not replace the full bound-evidence verification performed by the
normal freeze path. No forecast, model coefficient, or scorecard entry is
changed by this repair.

The existing seven forecasts use the pinned public WTA history through June 2
and remain `production_eligible=false`. The added Selekhmeteva–Kostovic match
was skipped by that runner and must not be counted as a prediction. This
repair does not create a FULL-STACK-FORWARD observation.
