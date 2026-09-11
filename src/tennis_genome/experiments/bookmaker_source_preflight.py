from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import cast

from tennis_genome.market.bookmaker_manifest import (
    BookmakerSourceFile,
    load_bookmaker_source_manifest,
    verify_bookmaker_source_manifest,
)
from tennis_genome.market.providers.bookmaker_historical import (
    SanitizedBookmakerQuote,
    load_tennis_data_quotes,
    load_valuebetennis_quotes,
    reject_post_2025_quotes,
)

_EXPERIMENT_ID = "MARKET-BOOK-SOURCE-PREFLIGHT-001"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"


@dataclass(frozen=True)
class SourceFileSummary:
    root_key: str
    source_family: str
    tour: str | None
    relative_path: str
    sha256: str
    row_count: int
    valid_quote_count: int
    invalid_quote_count: int
    min_match_date: str
    max_match_date: str


@dataclass(frozen=True)
class SourceYearSummary:
    source_family: str
    tour: str
    year: int
    row_count: int
    valid_quote_count: int
    invalid_quote_count: int


@dataclass(frozen=True)
class BookmakerSourcePreflightReport:
    experiment_id: str
    outcome_blind: bool
    confirmatory_result_free: bool
    market_policy: str
    bundle_sha256: str
    source_manifest_sha256: str
    included_file_count: int
    total_row_count: int
    total_valid_quote_count: int
    total_invalid_quote_count: int
    source_counts: dict[str, int]
    source_valid_quote_counts: dict[str, int]
    tour_counts: dict[str, int]
    tour_valid_quote_counts: dict[str, int]
    files: tuple[SourceFileSummary, ...]
    years: tuple[SourceYearSummary, ...]
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest_file_quotes(
    item: BookmakerSourceFile,
    *,
    valuebet_root: Path,
    tennis_data_atp_root: Path,
    tennis_data_wta_root: Path,
) -> list[SanitizedBookmakerQuote]:
    roots = {
        "valuebetennis": valuebet_root,
        "tennis_data_atp": tennis_data_atp_root,
        "tennis_data_wta": tennis_data_wta_root,
    }
    path = roots[item.root_key] / item.relative_path
    if item.source_family == "VALUEBETENNIS":
        quotes = load_valuebetennis_quotes(
            path,
            source_file=item.relative_path,
            source_file_sha256=item.sha256,
        )
    else:
        if item.tour not in {"ATP", "WTA"}:
            raise ValueError("Tennis-Data manifest file lacks ATP/WTA tour")
        quotes = load_tennis_data_quotes(
            path,
            tour=cast(str, item.tour),  # type: ignore[arg-type]
            source_file=item.relative_path,
            source_file_sha256=item.sha256,
        )
    reject_post_2025_quotes(quotes)
    if len(quotes) != item.row_count:
        raise ValueError(
            f"manifest row count changed for {item.root_key}/{item.relative_path}: "
            f"expected={item.row_count}, actual={len(quotes)}"
        )
    return quotes


def run_bookmaker_source_preflight(
    *,
    source_manifest_path: str | Path,
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
) -> BookmakerSourcePreflightReport:
    """Verify and summarize the frozen source bundle without using match outcomes.

    This diagnostic is intentionally upstream of canonical joins, QA denominators,
    signals, and settled winners. It proves only that the exact source snapshot can
    be parsed through the outcome firewall and reports quote availability by source,
    tour, and calendar year.
    """

    manifest = load_bookmaker_source_manifest(source_manifest_path)
    valuebet = Path(valuebet_root)
    atp_root = Path(tennis_data_atp_root)
    wta_root = Path(tennis_data_wta_root)
    verify_bookmaker_source_manifest(
        manifest,
        valuebet_root=valuebet,
        tennis_data_atp_root=atp_root,
        tennis_data_wta_root=wta_root,
    )

    file_summaries: list[SourceFileSummary] = []
    year_total: Counter[tuple[str, str, int]] = Counter()
    year_valid: Counter[tuple[str, str, int]] = Counter()
    source_total: Counter[str] = Counter()
    source_valid: Counter[str] = Counter()
    tour_total: Counter[str] = Counter()
    tour_valid: Counter[str] = Counter()

    for item in manifest.files:
        quotes = _load_manifest_file_quotes(
            item,
            valuebet_root=valuebet,
            tennis_data_atp_root=atp_root,
            tennis_data_wta_root=wta_root,
        )
        valid_count = sum(quote.quote_valid for quote in quotes)
        file_summaries.append(
            SourceFileSummary(
                root_key=item.root_key,
                source_family=item.source_family,
                tour=item.tour,
                relative_path=item.relative_path,
                sha256=item.sha256,
                row_count=len(quotes),
                valid_quote_count=valid_count,
                invalid_quote_count=len(quotes) - valid_count,
                min_match_date=min(quote.match_date for quote in quotes).isoformat(),
                max_match_date=max(quote.match_date for quote in quotes).isoformat(),
            )
        )
        for quote in quotes:
            key = (quote.source_family, quote.tour, quote.match_date.year)
            year_total[key] += 1
            source_total[quote.source_family] += 1
            tour_total[quote.tour] += 1
            if quote.quote_valid:
                year_valid[key] += 1
                source_valid[quote.source_family] += 1
                tour_valid[quote.tour] += 1

    years = tuple(
        SourceYearSummary(
            source_family=source,
            tour=tour,
            year=year,
            row_count=year_total[(source, tour, year)],
            valid_quote_count=year_valid[(source, tour, year)],
            invalid_quote_count=(
                year_total[(source, tour, year)] - year_valid[(source, tour, year)]
            ),
        )
        for source, tour, year in sorted(year_total)
    )
    total_rows = sum(source_total.values())
    total_valid = sum(source_valid.values())
    report = BookmakerSourcePreflightReport(
        experiment_id=_EXPERIMENT_ID,
        outcome_blind=True,
        confirmatory_result_free=True,
        market_policy=_MARKET_POLICY,
        bundle_sha256=manifest.bundle_sha256,
        source_manifest_sha256=_sha256_file(source_manifest_path),
        included_file_count=len(manifest.files),
        total_row_count=total_rows,
        total_valid_quote_count=total_valid,
        total_invalid_quote_count=total_rows - total_valid,
        source_counts=dict(sorted(source_total.items())),
        source_valid_quote_counts=dict(sorted(source_valid.items())),
        tour_counts=dict(sorted(tour_total.items())),
        tour_valid_quote_counts=dict(sorted(tour_valid.items())),
        files=tuple(sorted(file_summaries, key=lambda item: (item.root_key, item.relative_path))),
        years=years,
        artifact_sha256="",
    )
    unsigned = report.to_dict()
    unsigned.pop("artifact_sha256", None)
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return replace(report, artifact_sha256=artifact_hash)


def write_bookmaker_source_preflight(
    report: BookmakerSourcePreflightReport,
    path: str | Path,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and summarize the frozen bookmaker source bundle outcome-blind"
    )
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--valuebet-root", required=True, type=Path)
    parser.add_argument("--tennis-data-atp-root", required=True, type=Path)
    parser.add_argument("--tennis-data-wta-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_bookmaker_source_preflight(
        source_manifest_path=args.source_manifest,
        valuebet_root=args.valuebet_root,
        tennis_data_atp_root=args.tennis_data_atp_root,
        tennis_data_wta_root=args.tennis_data_wta_root,
    )
    write_bookmaker_source_preflight(report, args.output)
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
