from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

from tennis_genome.features.genome import GenomeVector


@dataclass(frozen=True)
class ResidualRecord:
    genome: GenomeVector
    residual_favorite: float


@dataclass(frozen=True)
class NeighborCandidate:
    match_id: str
    event_date: date
    distance: float
    residual_favorite: float
    player_a_id: str
    player_b_id: str


@dataclass(frozen=True)
class NeighborSummary:
    target_match_id: str
    k: int
    mean_residual: float
    nearest_distance: float
    mean_distance: float
    kth_distance: float
    shared_player_fraction: float
    neighbor_ids: tuple[str, ...]


def _raw_matrix(genomes: list[GenomeVector]) -> list[list[float]]:
    return [
        [float("nan") if value is None else float(value) for value in genome.values]
        for genome in genomes
    ]


def _shares_player(target: GenomeVector, candidate: NeighborCandidate) -> bool:
    target_players = {target.player_a_id, target.player_b_id}
    return (
        candidate.player_a_id in target_players
        or candidate.player_b_id in target_players
    )


class HistoricalGenomeIndex:
    """Leakage-safe historical Genome candidate pool.

    The constructor validates only immutable schema/population properties. Numeric
    preprocessing is deliberately deferred until a query supplies its target
    chronology. That lets the index prove that every candidate is strictly earlier
    than every target and that no target match is present before the imputer,
    scaler, or nearest-neighbor model sees any historical values.
    """

    def __init__(self, records: list[ResidualRecord]) -> None:
        if not records:
            raise ValueError("historical Genome index requires at least one record")
        first = records[0].genome
        feature_names = first.feature_names
        tour = first.tour
        if not feature_names:
            raise ValueError("Genome vectors must contain at least one feature")
        for record in records:
            genome = record.genome
            if genome.feature_names != feature_names:
                raise ValueError("historical Genome feature schemas differ")
            if genome.tour != tour:
                raise ValueError("historical Genome index cannot mix tours")

        match_ids = [record.genome.match_id for record in records]
        if len(match_ids) != len(set(match_ids)):
            raise ValueError("historical Genome index contains duplicate match IDs")

        self.records = tuple(records)
        self.feature_names = feature_names
        self.tour = tour
        self._record_match_ids = frozenset(match_ids)

    @property
    def size(self) -> int:
        return len(self.records)

    def _validate_target(self, genome: GenomeVector) -> None:
        if genome.tour != self.tour:
            raise ValueError("target tour does not match historical index tour")
        if genome.feature_names != self.feature_names:
            raise ValueError("target Genome feature schema differs from historical index")

    def _validate_query_chronology(self, targets: list[GenomeVector]) -> None:
        for genome in targets:
            self._validate_target(genome)

        target_ids = {genome.match_id for genome in targets}
        overlap = sorted(target_ids.intersection(self._record_match_ids))
        if overlap:
            raise ValueError(
                "target match ID is already present in historical Genome index: "
                + ", ".join(overlap[:5])
            )

        earliest_target_date = min(genome.event_date for genome in targets)
        invalid = sorted(
            record.genome.match_id
            for record in self.records
            if record.genome.event_date >= earliest_target_date
        )
        if invalid:
            raise ValueError(
                "historical Genome index requires every candidate to be strictly "
                "earlier than every queried target; invalid match IDs: "
                + ", ".join(invalid[:5])
            )

    def query_candidates(
        self,
        targets: list[GenomeVector],
        *,
        candidate_limit: int = 1000,
    ) -> list[tuple[NeighborCandidate, ...]]:
        if candidate_limit <= 0:
            raise ValueError("candidate_limit must be positive")
        if not targets:
            return []

        # Temporal/self-neighbor safety is checked before any historical values are
        # used to fit imputation, scaling, or nearest-neighbor preprocessing.
        self._validate_query_chronology(targets)

        imputer = SimpleImputer(
            strategy="median",
            add_indicator=False,
            keep_empty_features=True,
        )
        historical_raw = _raw_matrix([record.genome for record in self.records])
        historical_imputed = imputer.fit_transform(historical_raw)
        scaler = StandardScaler()
        historical_standardized = np.asarray(
            scaler.fit_transform(historical_imputed),
            dtype=float,
        )
        target_raw = _raw_matrix(targets)
        target_imputed = imputer.transform(target_raw)
        target_matrix = np.asarray(scaler.transform(target_imputed), dtype=float)

        count = min(candidate_limit, self.size)
        model = NearestNeighbors(
            n_neighbors=count,
            algorithm="brute",
            metric="euclidean",
            n_jobs=-1,
        )
        model.fit(historical_standardized)
        distances, indices = model.kneighbors(target_matrix, return_distance=True)

        result: list[tuple[NeighborCandidate, ...]] = []
        for distance_row, index_row in zip(distances, indices, strict=True):
            candidates: list[NeighborCandidate] = []
            for distance, index in zip(distance_row, index_row, strict=True):
                record = self.records[int(index)]
                genome = record.genome
                candidates.append(
                    NeighborCandidate(
                        match_id=genome.match_id,
                        event_date=genome.event_date,
                        distance=float(distance),
                        residual_favorite=float(record.residual_favorite),
                        player_a_id=genome.player_a_id,
                        player_b_id=genome.player_b_id,
                    )
                )
            candidates.sort(key=lambda item: (item.distance, item.match_id))
            result.append(tuple(candidates))
        return result

    def summarize(
        self,
        target: GenomeVector,
        candidates: tuple[NeighborCandidate, ...],
        *,
        k: int,
        exclude_shared_players: bool = False,
    ) -> NeighborSummary | None:
        self._validate_target(target)
        if k <= 0:
            raise ValueError("k must be positive")
        if any(candidate.match_id == target.match_id for candidate in candidates):
            raise ValueError("target match cannot be its own historical neighbor")
        if any(candidate.event_date >= target.event_date for candidate in candidates):
            raise ValueError("historical neighbor is not strictly earlier than target")
        selected_pool = [
            candidate
            for candidate in candidates
            if not exclude_shared_players or not _shares_player(target, candidate)
        ]
        if len(selected_pool) < k:
            return None
        selected = selected_pool[:k]
        distances = [candidate.distance for candidate in selected]
        shared_count = sum(_shares_player(target, candidate) for candidate in selected)
        return NeighborSummary(
            target_match_id=target.match_id,
            k=k,
            mean_residual=(
                sum(candidate.residual_favorite for candidate in selected) / k
            ),
            nearest_distance=distances[0],
            mean_distance=sum(distances) / k,
            kth_distance=distances[-1],
            shared_player_fraction=shared_count / k,
            neighbor_ids=tuple(candidate.match_id for candidate in selected),
        )
