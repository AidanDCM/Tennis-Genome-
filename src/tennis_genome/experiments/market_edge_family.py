from __future__ import annotations

from dataclasses import asdict, dataclass

from tennis_genome.evaluation.multiple_testing import HolmResult, holm_adjust
from tennis_genome.experiments.market_edge import (
    MarketEdgeClaimReport,
    MarketSignalRow,
    SignalName,
    Tour,
    run_market_edge_claim,
)

_CLAIMS: tuple[tuple[Tour, SignalName], ...] = (
    ("ATP", "profile_gap"),
    ("WTA", "profile_gap"),
    ("ATP", "genome"),
    ("WTA", "genome"),
)


@dataclass(frozen=True)
class FamilyClaimDecision:
    label: str
    tour: Tour
    signal_name: SignalName
    brier_holm: HolmResult
    log_loss_holm: HolmResult
    pre_holm_candidate_pass: bool
    holm_brier_pass: bool
    holm_log_loss_pass: bool
    market_incremental_pass: bool


@dataclass(frozen=True)
class MarketEdgeFamilyReport:
    experiment_id: str
    multiplicity_method: str
    claims: tuple[MarketEdgeClaimReport, ...]
    decisions: tuple[FamilyClaimDecision, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def claim_label(tour: Tour, signal_name: SignalName) -> str:
    return f"{tour}:{signal_name}"


def run_market_edge_family(
    claim_rows: dict[tuple[Tour, SignalName], list[MarketSignalRow]],
    *,
    min_prior_rows: int = 1000,
) -> MarketEdgeFamilyReport:
    expected = set(_CLAIMS)
    supplied = set(claim_rows)
    if supplied != expected:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise ValueError(
            f"MARKET-EDGE-001 requires the frozen four-claim family; "
            f"missing={missing}, extra={extra}"
        )

    reports: list[MarketEdgeClaimReport] = []
    for tour, signal_name in _CLAIMS:
        rows = claim_rows[(tour, signal_name)]
        if any(row.tour != tour for row in rows):
            raise ValueError(f"{claim_label(tour, signal_name)} contains wrong-tour rows")
        reports.append(
            run_market_edge_claim(
                rows,
                signal_name=signal_name,
                min_prior_rows=min_prior_rows,
            )
        )

    brier_adjusted = holm_adjust(
        {
            claim_label(report.tour, report.signal_name): (report.brier_inference.sign_flip.p_value)
            for report in reports
        }
    )
    log_adjusted = holm_adjust(
        {
            claim_label(report.tour, report.signal_name): (
                report.log_loss_inference.sign_flip.p_value
            )
            for report in reports
        }
    )

    decisions: list[FamilyClaimDecision] = []
    for report in reports:
        label = claim_label(report.tour, report.signal_name)
        brier = brier_adjusted[label]
        log_loss = log_adjusted[label]
        pre_holm = report.promotion_diagnostics.pre_holm_candidate_pass
        decisions.append(
            FamilyClaimDecision(
                label=label,
                tour=report.tour,
                signal_name=report.signal_name,
                brier_holm=brier,
                log_loss_holm=log_loss,
                pre_holm_candidate_pass=pre_holm,
                holm_brier_pass=brier.adjusted_p_value < 0.05,
                holm_log_loss_pass=log_loss.adjusted_p_value < 0.05,
                market_incremental_pass=bool(
                    pre_holm and brier.adjusted_p_value < 0.05 and log_loss.adjusted_p_value < 0.05
                ),
            )
        )

    return MarketEdgeFamilyReport(
        experiment_id="MARKET-EDGE-001",
        multiplicity_method="Holm FWER separately for Brier and log-loss claim families",
        claims=tuple(reports),
        decisions=tuple(decisions),
    )
