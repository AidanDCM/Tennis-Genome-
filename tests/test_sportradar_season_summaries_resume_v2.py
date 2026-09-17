from datetime import UTC, datetime
from pathlib import Path

from tennis_genome.research_workbench.sportradar_season_summaries_census import (
    ProviderHttpResponse,
)
from tennis_genome.research_workbench.sportradar_season_summaries_resume_v2 import (
    resume_season_summaries_census,
)


def test_resume_v2_entrypoint_is_importable_and_requires_nonempty_api_key(tmp_path: Path) -> None:
    try:
        resume_season_summaries_census(
            inventory_path=tmp_path / "missing-inventory.json",
            partial_census_root=tmp_path / "missing-partial",
            output_dir=tmp_path / "out",
            access_level="trial",
            api_key="",
            provider_get=lambda _url, _headers: ProviderHttpResponse(
                status=500,
                body=b"{}",
                headers=(),
            ),
            sleeper=lambda _seconds: None,
            now=lambda: datetime(2026, 9, 17, 15, 0, tzinfo=UTC),
        )
    except ValueError as exc:
        assert "SPORTRADAR_API_KEY" in str(exc)
    else:
        raise AssertionError("empty provider key should fail closed")
