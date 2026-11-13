# 2026-11-13 WTA shadow baseline coverage gate audit (read-only)

## Sources and evidence tier
Main commit `40bb697ec786527b7ed1a4c67d6d0a92aea17782`; scorecard `web-shadow/scorecard.json` blob `c9636ac9d86c256ccf241e652b9456034c451fc3`. Workflow `.github/workflows/wta_web_shadow_results.yml` blob `f49387bb740a664ef5a72ee850203301062dbf2a`, schedule `41 * * * *`, fail-closed existing-proposal/orphan gate. This is **non-production WTA Web Shadow**, `production_eligible=false`. Frozen champion digest and qualified production-forward N not independently retrieved; do not extrapolate.

## Falsifiable experiment (no fitting or outcome edits)
H0: every SETTLED scorecard prediction with a `baseline_path` is included in the scorecard's paired Elo comparison (path presence is sufficient for pairing). Alternative: there are settled baseline-path records excluded by additional eligibility criteria. Compare counts using immutable scorecard only. Reject H0 if counts differ; do not infer the reason for exclusion from path presence alone.

Actual connected GitHub `fetch_file` read and JavaScript JSON parsing: 29 slates, 104 prediction entries, 89 SETTLED, 15 PENDING, zero duplicate match IDs. Exactly 82 SETTLED entries have a `baseline_path`; paired comparison `baseline_comparison.settled_match_count=79`. **H0 rejected; difference=3**. All 89 SETTLED entries have settlement paths and result hashes. Seven SETTLED have no baseline path; these seven IDs are:
- `web:wta:singapore:2026:RS007`
- `web:wta:seoul:2026:qfnl:ma-lee`
- `web:wta:seoul:2026:qfnl:shubladze-astakhova`
- `web:wta:seoul:2026:qfnl:yao-kuramochi`
- `web:wta:seoul:2026:qfnl:ibragimova-saito`
- `web:wta:singapore:2026:RS005`
- `web:wta:singapore:2026:RS006`

Additional **coverage diagnostic**: all 15 PENDING entries have baseline paths; 9 Seoul, 4 Singapore, 2 event group 1074. The 13 legacy Seoul/Singapore pending IDs and 2 group-1074 IDs remain unqualified. Earliest pending scheduled start 2026-09-22T11:00:00+08:00, latest 2026-11-04T14:00:00+08:00. Pending is not a known loss or a settlement. Scorecard has 86 primary scored, 47 correct, Brier 0.2513224181341722, log loss 0.6966212008671667; 79 common Genome–Elo with Brier 0.2522696014990375 vs 0.2578582137265702 and log loss 0.6983470279140795 vs 0.7186905603048556, but accuracy 42/79 vs 43/79. No per-match paired uncertainty computed.

## Reproduction
```python
import json
s=json.load(open("web-shadow/scorecard.json"))
p=[x for slate in s["slates"] for x in slate["predictions"]]
settled=[x for x in p if x["status"]=="SETTLED"]
pending=[x for x in p if x["status"]=="PENDING"]
assert len(p)==104 and len(set(x["match_id"] for x in p))==104
assert len(settled)==89 and len(pending)==15
assert sum("baseline_path" in x for x in settled)==82
assert s["baseline_comparison"]["settled_match_count"]==79
assert sum("baseline_path" not in x for x in settled)==7
assert all("baseline_path" in x for x in pending)
print("PASS: 82 baseline-path settled vs 79 paired; 3 eligibility gaps")
```
Run with `python - <<'PY'` followed by the above body and `PY`. The equivalent assertions were evaluated against GitHub-fetched scorecard JSON in JavaScript in this iteration, not by a repository Python test suite.

## Interpretation and negative evidence
A baseline file path does **not** certify a valid comparable baseline forecast. The three-record difference could reflect absent, invalid, or nonqualifying baseline contents, or other scorecard rules. No source files for those three were independently adjudicated here. Do not fill missing outcomes or assume selection is random. No new challenger, model ablation, CI, settlement or champion change.

## External methodological research
- Chang & Wiens (ICML 2024), [From Biased Selective Labels to Pseudo-Labels](https://proceedings.mlr.press/v235/chang24e.html): selection-biased outcome observation can distort model assessment; clinical population, not tennis. Research only, no code imported, license not established.
- Loveday, Taggart & Khanarmuei (Weather and Forecasting, Aug 2024), [A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts](https://doi.org/10.1175/WAF-D-23-0201.1): proper scores versus winner classifications; weather population, AMS reuse terms, no code imported.
- Contrary caution: Kang & Schafer (2008), [Demystifying Double Robustness](https://arxiv.org/abs/0804.2958): incorrect missingness models can undermine weighting corrections; no justification for propensity weighting without validated missingness mechanism. No implementation license assumed.

## Prioritized next executable queue
1. Read `scripts` scorecard baseline eligibility implementation and each of 82 settled baseline JSON files, identify exact three excluded IDs and failure reasons; verify prediction hashes/timestamps, negative controls, no mutation.
2. Execute exact-head pytest/Ruff for any code change; keep draft PR separate from production.
3. Audit official source acquisition and identity/round mismatch for 12 legacy candidates; independent pre-start and tournament adjudication before any settlement.
4. Refresh champion digest and qualified forward N, capture newly locked prospective observations, then paired chronological Brier/log-loss/accuracy intervals and calibration by tour/surface/time; leave final holdout untouched.

## Follow-up source-level root cause check (same iteration)
Read `scripts/apply_web_shadow_settlement_batch.py` blob `eeb98a1259b61dfc32aaf177da31d3622b9a70f4`, lines 140–188: after counting every SETTLED scorecard entry, it loads its settlement and executes `if not _settlement_is_evaluation_eligible(settlement): continue` **before** adding a Genome metrics row or loading any baseline. Read `scripts/validate_web_shadow_scorecard.py` blob `62d32b2580fb33b4432d41e05d092b4d16c70dd1`: `_settlement_is_evaluation_eligible` returns true only for status `COMPLETED` and rejects unsupported statuses. This explains the denominator gate: 89 SETTLED entries, 86 evaluation-eligible, 82 baseline-path SETTLED entries, 79 evaluation-eligible paired entries. Therefore the three-record discrepancy is **consistent with** three baseline-path entries carrying terminal non-COMPLETED statuses. Individual settlement files and the three IDs have **not** yet been inspected, so do not assert their specific status or identity. This supersedes the earlier description of the three as unexplained at the code-path level; per-record adjudication remains open.

Reproduction: inspect `sed -n '140,188p' scripts/apply_web_shadow_settlement_batch.py` and `grep -A7 '^def _settlement_is_evaluation_eligible' scripts/validate_web_shadow_scorecard.py`. Code-path review is not an executed pytest/CI run.
