from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    SeasonSummariesCensus,
)
from tennis_genome.research_workbench.sportradar_timeline_audit_sample import (
    build_timeline_audit_sample_plan,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the preregistered whole-season Sportradar timeline audit sample"
    )
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--census", required=True, type=Path)
    parser.add_argument("--request-budget-cap", required=True, type=int)
    parser.add_argument("--max-seasons", type=int, default=12)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    census = SeasonSummariesCensus.model_validate_json(
        args.census.read_text(encoding="utf-8")
    )
    plan = build_timeline_audit_sample_plan(
        inventory_content=args.inventory.read_bytes(),
        census=census,
        request_budget_cap=args.request_budget_cap,
        max_seasons=args.max_seasons,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(plan.canonical_payload(), indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    args.output.with_suffix(".sha256").write_text(digest + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sample_plan_semantic_sha256": plan.semantic_sha256,
                "sample_plan_file_sha256": digest,
                "selected_season_count": plan.selected_season_count,
                "selected_timeline_count": plan.selected_timeline_count,
                "covered_tour_era_strata": list(plan.covered_tour_era_strata),
                "unavailable_tour_era_strata": list(plan.unavailable_tour_era_strata),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
