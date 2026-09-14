# Forecast Research Workbench

Status: **development foundation only**

This package creates a bounded research surface for Tennis Genome v2 work without modifying the frozen TGE-Independent-v1 predictor, FULL-STACK-FORWARD-001, or PATTERN-CONFIRM-001.

## Primary object

The workbench treats a complete, reproducible `ForecastingProcedureSpec` as the primary research object. A pattern, rule, trajectory, latent state, calibration layer, or historical-similarity method is only useful if it becomes part of a procedure that improves future probability forecasts under protected evaluation.

This deliberately avoids making a catalog of discovered rules the center of the system.

## Current v0 scope

The first slice provides:

- immutable forecasting-procedure specifications;
- frozen evaluation specifications;
- a market-blind research boundary;
- an exposure/dependency graph for adaptive research lineage;
- content-addressed immutable research records;
- proper-score evaluation using Brier score and log loss;
- reproducible synthetic benchmark worlds for null, calibration-error, and planted-interaction cases.

It does **not** yet provide:

- broad pattern generation;
- dynamic serve/return state estimation;
- historical chronological forecast-panel construction;
- real protected evaluation data;
- AI research agents;
- market-edge analysis;
- any modification to the frozen production predictor.

## Scientific boundary

Chronological out-of-fold forecasts are necessary for later residual research, but they are not automatically independent evidence. Any decision made after viewing outcomes, residual plots, aggregate metrics, or protected results creates research exposure that later procedures inherit.

The `ExposureGraph` records that dependency explicitly. Protected evaluation should fail closed when a challenger inherits exposure to the same protected source population.

## Independent probability boundary

Workbench procedures are for independent tennis probability research only. Procedure input contracts, feature names, and required data reject downstream market semantics such as bookmaker odds, sportsbook data, stakes, profits, CLV, or wagering fields.

Market research remains a separate downstream experiment.

## Synthetic benchmark principle

Before broad discovery, the research process must be tested in worlds where the truth is known.

The initial benchmark set contains:

1. `null_world`: the baseline already equals the true conditional probability; no residual correction should be necessary.
2. `miscalibration_world`: the baseline has a global calibration defect but no special subgroup rule is required.
3. `interaction_world`: the baseline omits a real nonlinear interaction, so residual information genuinely exists.

Additional worlds should later add adaptive-threshold selection, shared player/tournament dependence, future-smoothed leakage, provider drift, missingness artifacts, rare signals, regime shifts, and prospective collapse.

## Next engineering slices

1. Historical availability audit and explicit feature-availability contracts.
2. Leakage-safe chronological forecast panels.
3. Persistent exposure/dependency manifests tied to research decisions.
4. `CHALLENGER-BASELINE-001`: frozen baseline vs calibration-only vs smooth correction vs shallow nonlinear challenger vs dynamic serve/return challenger.
5. Dynamic player-state research.
6. Bounded residual discovery only if simpler challengers justify additional complexity.

## Non-goals

This foundation is not a claim that a Pattern Intelligence Engine has been validated, that a sportsbook edge exists, or that the current predictor should change. The larger search system must earn its scope by producing protected forecast improvements that simpler procedures cannot match.
