# Forecast Research Workbench

Status: **development foundation with protected-evaluation integrity enforcement**

This package creates a bounded research surface for Tennis Genome v2 work without modifying the frozen TGE-Independent-v1 predictor, FULL-STACK-FORWARD-001, or PATTERN-CONFIRM-001.

## Primary object

The workbench treats a complete, reproducible `ForecastingProcedureSpec` as the primary research object. A pattern, rule, trajectory, latent state, calibration layer, or historical-similarity method is only useful if it becomes part of a procedure that improves future probability forecasts under protected evaluation.

This deliberately avoids making a catalog of discovered rules the center of the system.

## Current v0 scope

The current foundation provides:

- immutable forecasting-procedure specifications;
- frozen evaluation specifications;
- a market-blind research boundary;
- an exposure/dependency graph for adaptive research lineage;
- mandatory protected-evaluation exposure checks;
- content-addressed immutable research records;
- procedure-hash and evaluation-hash binding in canonical score results;
- proper-score evaluation using Brier score and log loss;
- reproducible synthetic benchmark worlds for null, calibration-error, and planted-interaction cases.

It does **not** yet provide:

- broad pattern generation;
- dynamic serve/return state estimation;
- historical chronological forecast-panel construction;
- real protected evaluation data;
- trial-family accounting;
- complete dataset/code fingerprint objects;
- AI research agents;
- market-edge analysis;
- any modification to the frozen production predictor.

## Scientific boundary

Chronological out-of-fold forecasts are necessary for later residual research, but they are not automatically independent evidence. Any decision made after viewing outcomes, residual plots, aggregate metrics, or protected results creates research exposure that later procedures inherit.

The `ExposureGraph` records that dependency explicitly. A protected `EvaluationSpec` must declare the source population it protects. The forecasting procedure must declare at least one registered development exposure record, every declared exposure ID must resolve in the supplied graph, and inherited exposure may not overlap the protected source population. The public probability evaluator fails closed when any of those requirements is missing or violated.

This closes the first enforcement gap identified in the independent audit: exposure lineage is no longer a stand-alone data structure that protected scoring can ignore.

The graph can verify declared lineage and inherited overlap. It cannot prove that a human or external agent disclosed every piece of information they observed. Future research automation should therefore make exposure capture part of the workflow rather than relying on retrospective manual declarations.

## Independent probability boundary

Workbench procedures are for independent tennis probability research only. Market-semantic checks cover procedure identity and descriptive fields, input contracts, feature names, training method, hyperparameters, calibration, prediction method, and required data. Downstream concepts such as bookmaker odds, sportsbook data, implied probabilities, stakes, profits, CLV, or wagering fields are rejected.

Market research remains a separate downstream experiment.

## Synthetic benchmark principle

Before broad discovery, the research process must be tested in worlds where the truth is known.

The initial benchmark set contains:

1. `null_world`: the baseline already equals the true conditional probability; no residual correction should be necessary.
2. `miscalibration_world`: the baseline has a global calibration defect but no special subgroup rule is required.
3. `interaction_world`: the baseline omits a real nonlinear interaction, so residual information genuinely exists.

The worlds are currently reproducible known-truth fixtures. The next slice must close the loop by fitting/evaluating real challenger procedures against them and asserting the expected scientific conclusions rather than testing only fixture construction.

Additional worlds should later add adaptive-threshold selection, shared player/tournament dependence, future-smoothed leakage, provider drift, missingness artifacts, rare signals, regime shifts, and prospective collapse.

## Next engineering slices

1. Close the synthetic-world validation loop with actual challenger procedures.
2. Build prospective eligible-event census / denominator completeness controls.
3. Add procedure-search trial families, canonical dataset/code fingerprints, and protected-population burn.
4. Audit historical availability and add explicit feature-availability contracts.
5. Build leakage-safe chronological forecast panels.
6. Develop dynamic serve/return state as a possible Core-v2 state-estimation challenger.
7. Run bounded challenger comparisons only after the integrity substrate is complete.
8. Expand residual/pattern discovery only if simpler challengers leave meaningful protected signal.

## Non-goals

This foundation is not a claim that a Pattern Intelligence Engine has been validated, that a sportsbook edge exists, or that the current predictor should change. The larger search system must earn its scope by producing protected forecast improvements that simpler procedures cannot match.
