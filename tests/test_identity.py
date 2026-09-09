from tennis_genome.data.identity import canonical_player_id, normalize_player_name, orient_pair


def test_name_normalization_is_stable():
    assert normalize_player_name("  João   Silva ") == "joao silva"


def test_fallback_identity_is_tour_scoped():
    atp = canonical_player_id(tour="ATP", source_id=None, name="Alex Smith")
    wta = canonical_player_id(tour="WTA", source_id=None, name="Alex Smith")
    assert atp != wta


def test_orientation_is_independent_of_winner_first_layout():
    player_a_id, player_b_id, _, _, a_won = orient_pair(
        winner_id="atp:id:200",
        loser_id="atp:id:100",
        winner_name="Winner",
        loser_name="Loser",
    )
    assert player_a_id == "atp:id:100"
    assert player_b_id == "atp:id:200"
    assert a_won is False


def test_orientation_can_make_a_the_winner_without_forcing_it():
    player_a_id, player_b_id, _, _, a_won = orient_pair(
        winner_id="atp:id:100",
        loser_id="atp:id:200",
        winner_name="Winner",
        loser_name="Loser",
    )
    assert player_a_id == "atp:id:100"
    assert player_b_id == "atp:id:200"
    assert a_won is True
