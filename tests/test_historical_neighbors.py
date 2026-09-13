from __future__ import annotations

from datetime import date

import pytest

from tennis_genome.features.genome import GenomeVector
from tennis_genome.neighbors.historical import HistoricalGenomeIndex, ResidualRecord


def _genome(
    match_id: str,
    values: tuple[float | None, ...],
    *,
    player_a_id: str,
    player_b_id: str,
    event_date: date = date(2020, 1, 1),
    feature_names: tuple[str, ...] = ("x", "y"),
) -> GenomeVector:
    return GenomeVector(
        match_id=match_id,
        event_date=event_date,
        tour="ATP",
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        orientation_sign=1,
        feature_names=feature_names,
        values=values,
    )


def _record(
    match_id: str,
    values: tuple[float | None, ...],
    residual: float,
    *,
    player_a_id: str,
    player_b_id: str,
    event_date: date = date(2020, 1, 1),
) -> ResidualRecord:
    return ResidualRecord(
        genome=_genome(
            match_id,
            values,
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            event_date=event_date,
        ),
        residual_favorite=residual,
    )


def _target(
    match_id: str,
    values: tuple[float | None, ...],
    *,
    player_a_id: str,
    player_b_id: str,
    event_date: date = date(2021, 1, 1),
    feature_names: tuple[str, ...] = ("x", "y"),
) -> GenomeVector:
    return _genome(
        match_id,
        values,
        player_a_id=player_a_id,
        player_b_id=player_b_id,
        event_date=event_date,
        feature_names=feature_names,
    )


def test_equal_distance_candidates_are_ordered_by_match_id() -> None:
    index = HistoricalGenomeIndex(
        [
            _record("z", (0.0, 0.0), 0.1, player_a_id="p1", player_b_id="p2"),
            _record("a", (2.0, 0.0), -0.1, player_a_id="p3", player_b_id="p4"),
        ]
    )
    target = _target(
        "target",
        (1.0, 0.0),
        player_a_id="x",
        player_b_id="y",
    )

    candidates = index.query_candidates([target], candidate_limit=2)[0]

    assert candidates[0].distance == pytest.approx(candidates[1].distance)
    assert [candidate.match_id for candidate in candidates] == ["a", "z"]


def test_neighbor_summary_uses_registered_unweighted_residual_mean() -> None:
    index = HistoricalGenomeIndex(
        [
            _record("m1", (0.0, 0.0), 0.20, player_a_id="p1", player_b_id="p2"),
            _record("m2", (1.0, 0.0), -0.10, player_a_id="p3", player_b_id="p4"),
            _record("m3", (2.0, 0.0), 0.05, player_a_id="p5", player_b_id="p6"),
        ]
    )
    target = _target(
        "target",
        (0.4, 0.0),
        player_a_id="x",
        player_b_id="y",
    )
    candidates = index.query_candidates([target], candidate_limit=3)[0]
    summary = index.summarize(target, candidates, k=2)

    assert summary is not None
    assert summary.k == 2
    selected_residuals = [
        candidate.residual_favorite
        for candidate in candidates[:2]
    ]
    assert summary.mean_residual == pytest.approx(sum(selected_residuals) / 2)
    assert summary.kth_distance >= summary.nearest_distance


def test_shared_player_exclusion_filters_identity_neighbors() -> None:
    index = HistoricalGenomeIndex(
        [
            _record("shared", (0.0, 0.0), 0.4, player_a_id="target-a", player_b_id="p2"),
            _record("clean-1", (0.2, 0.0), 0.1, player_a_id="p3", player_b_id="p4"),
            _record("clean-2", (0.4, 0.0), -0.1, player_a_id="p5", player_b_id="p6"),
        ]
    )
    target = _target(
        "target",
        (0.0, 0.0),
        player_a_id="target-a",
        player_b_id="target-b",
    )
    candidates = index.query_candidates([target], candidate_limit=3)[0]

    primary = index.summarize(target, candidates, k=2)
    excluded = index.summarize(
        target,
        candidates,
        k=2,
        exclude_shared_players=True,
    )

    assert primary is not None
    assert primary.shared_player_fraction == pytest.approx(0.5)
    assert excluded is not None
    assert excluded.shared_player_fraction == 0.0
    assert "shared" not in excluded.neighbor_ids


def test_shared_player_sensitivity_returns_none_when_too_few_clean_neighbors() -> None:
    index = HistoricalGenomeIndex(
        [
            _record("m1", (0.0, 0.0), 0.1, player_a_id="target-a", player_b_id="p1"),
            _record("m2", (1.0, 0.0), 0.1, player_a_id="target-b", player_b_id="p2"),
        ]
    )
    target = _target(
        "target",
        (0.5, 0.0),
        player_a_id="target-a",
        player_b_id="target-b",
    )
    candidates = index.query_candidates([target], candidate_limit=2)[0]

    assert index.summarize(
        target,
        candidates,
        k=1,
        exclude_shared_players=True,
    ) is None


def test_target_values_never_refit_historical_preprocessing() -> None:
    records = [
        _record("m1", (0.0, 0.0), 0.1, player_a_id="p1", player_b_id="p2"),
        _record("m2", (2.0, 0.0), -0.1, player_a_id="p3", player_b_id="p4"),
    ]
    index = HistoricalGenomeIndex(records)
    ordinary = _target(
        "ordinary",
        (1.0, 0.0),
        player_a_id="x",
        player_b_id="y",
    )
    extreme = _target(
        "extreme",
        (1_000_000.0, 0.0),
        player_a_id="q",
        player_b_id="r",
    )

    before = index.query_candidates([ordinary], candidate_limit=2)[0]
    index.query_candidates([extreme], candidate_limit=2)
    after = index.query_candidates([ordinary], candidate_limit=2)[0]

    assert before == after


def test_index_rejects_mixed_feature_schemas() -> None:
    first = _record("m1", (0.0, 0.0), 0.1, player_a_id="p1", player_b_id="p2")
    second = ResidualRecord(
        genome=_genome(
            "m2",
            (1.0,),
            player_a_id="p3",
            player_b_id="p4",
            feature_names=("other",),
        ),
        residual_favorite=-0.1,
    )

    with pytest.raises(ValueError, match="feature schemas differ"):
        HistoricalGenomeIndex([first, second])


def test_index_rejects_duplicate_historical_match_ids() -> None:
    records = [
        _record("duplicate", (0.0, 0.0), 0.1, player_a_id="p1", player_b_id="p2"),
        _record("duplicate", (1.0, 0.0), -0.1, player_a_id="p3", player_b_id="p4"),
    ]

    with pytest.raises(ValueError, match="duplicate match IDs"):
        HistoricalGenomeIndex(records)


def test_query_rejects_target_match_already_in_index() -> None:
    index = HistoricalGenomeIndex(
        [
            _record(
                "target",
                (0.0, 0.0),
                0.1,
                player_a_id="p1",
                player_b_id="p2",
                event_date=date(2019, 1, 1),
            ),
            _record(
                "other",
                (1.0, 0.0),
                -0.1,
                player_a_id="p3",
                player_b_id="p4",
                event_date=date(2020, 1, 1),
            ),
        ]
    )
    target = _target(
        "target",
        (0.5, 0.0),
        player_a_id="x",
        player_b_id="y",
        event_date=date(2021, 1, 1),
    )

    with pytest.raises(ValueError, match="target match ID"):
        index.query_candidates([target], candidate_limit=2)


def test_query_rejects_same_day_and_future_rows_before_preprocessing() -> None:
    index = HistoricalGenomeIndex(
        [
            _record(
                "prior",
                (0.0, 0.0),
                0.1,
                player_a_id="p1",
                player_b_id="p2",
                event_date=date(2020, 12, 31),
            ),
            _record(
                "same-day",
                (999999.0, 0.0),
                -0.1,
                player_a_id="p3",
                player_b_id="p4",
                event_date=date(2021, 1, 1),
            ),
            _record(
                "future",
                (-999999.0, 0.0),
                0.2,
                player_a_id="p5",
                player_b_id="p6",
                event_date=date(2021, 1, 2),
            ),
        ]
    )
    target = _target(
        "target",
        (0.5, 0.0),
        player_a_id="x",
        player_b_id="y",
        event_date=date(2021, 1, 1),
    )

    assert not hasattr(index, "_imputer")
    assert not hasattr(index, "_scaler")
    with pytest.raises(ValueError, match="strictly earlier"):
        index.query_candidates([target], candidate_limit=3)
    assert not hasattr(index, "_imputer")
    assert not hasattr(index, "_scaler")


def test_query_rejects_batch_if_history_is_future_for_any_target() -> None:
    index = HistoricalGenomeIndex(
        [
            _record(
                "historical",
                (0.0, 0.0),
                0.1,
                player_a_id="p1",
                player_b_id="p2",
                event_date=date(2020, 6, 1),
            )
        ]
    )
    early = _target(
        "early",
        (0.1, 0.0),
        player_a_id="a",
        player_b_id="b",
        event_date=date(2020, 5, 1),
    )
    later = _target(
        "later",
        (0.2, 0.0),
        player_a_id="c",
        player_b_id="d",
        event_date=date(2021, 1, 1),
    )

    with pytest.raises(ValueError, match="strictly earlier"):
        index.query_candidates([later, early], candidate_limit=1)
