from __future__ import annotations

from tennis_genome.data.canonical import MatchStats

from .api_tennis_enrichment import ApiTennisMatchEnrichment


def _match_id(record: ApiTennisMatchEnrichment) -> str:
    return f"api-tennis:{record.event_key}"


def api_tennis_enrichment_to_match_stats(
    record: ApiTennisMatchEnrichment,
) -> MatchStats:
    """Convert admitted API-Tennis post-match evidence into canonical MatchStats.

    The bridge deliberately preserves provider counts rather than reconstructing
    or smoothing inconsistent denominators. Scheduled match time remains outside
    MatchStats and is never promoted to actual-start chronology.
    """

    a = record.player_a_stats
    b = record.player_b_stats

    if a.service_points_total != b.return_points_total:
        raise ValueError("player A service total does not match player B return total")
    if b.service_points_total != a.return_points_total:
        raise ValueError("player B service total does not match player A return total")

    if a.first_serve_points_won + a.second_serve_points_won > a.service_points_total:
        raise ValueError("player A service-points-won counts exceed service total")
    if b.first_serve_points_won + b.second_serve_points_won > b.service_points_total:
        raise ValueError("player B service-points-won counts exceed service total")

    return MatchStats(
        match_id=_match_id(record),
        aces_a=a.aces,
        aces_b=b.aces,
        double_faults_a=a.double_faults,
        double_faults_b=b.double_faults,
        service_points_a=a.service_points_total,
        service_points_b=b.service_points_total,
        first_serves_in_a=a.first_serve_points_total,
        first_serves_in_b=b.first_serve_points_total,
        first_serve_points_won_a=a.first_serve_points_won,
        first_serve_points_won_b=b.first_serve_points_won,
        second_serve_points_won_a=a.second_serve_points_won,
        second_serve_points_won_b=b.second_serve_points_won,
        service_games_a=a.service_games_total,
        service_games_b=b.service_games_total,
        break_points_saved_a=a.break_points_saved,
        break_points_saved_b=b.break_points_saved,
        break_points_faced_a=a.break_points_faced,
        break_points_faced_b=b.break_points_faced,
        duration_minutes=None,
    )
