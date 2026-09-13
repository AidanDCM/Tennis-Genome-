from __future__ import annotations

from dataclasses import dataclass

from tennis_genome.market.historical_join import normalize_market_player_name


@dataclass(frozen=True)
class TennisDataAlias:
    surname_tokens: tuple[str, ...]
    initials: str


def _letters(value: str) -> str:
    return "".join(char for char in value if char.isalpha())


def parse_tennis_data_abbreviation(value: str) -> TennisDataAlias | None:
    """Parse the preregistered Tennis-Data surname + initials convention."""

    raw_tokens = value.strip().split()
    if len(raw_tokens) < 2:
        return None
    final = raw_tokens[-1]
    letters = _letters(final)
    abbreviated = "." in final or (bool(letters) and letters.isupper() and 1 <= len(letters) <= 3)
    if not abbreviated or not letters:
        return None
    surname = normalize_market_player_name(" ".join(raw_tokens[:-1])).split()
    if not surname:
        return None
    return TennisDataAlias(
        surname_tokens=tuple(surname),
        initials=letters.casefold(),
    )


def _contiguous_positions(
    haystack: list[str],
    needle: tuple[str, ...],
) -> tuple[int, ...]:
    if not needle or len(needle) > len(haystack):
        return ()
    width = len(needle)
    return tuple(
        start
        for start in range(1, len(haystack) - width + 1)
        if tuple(haystack[start : start + width]) == needle
    )


def _prefix_initial_candidates(prefix: list[str]) -> set[str]:
    if not prefix:
        return set()
    values = {
        "".join(token[0] for token in prefix if token),
        prefix[0][0],
    }
    if len(prefix) == 1 and 1 <= len(prefix[0]) <= 3:
        values.add(prefix[0])
    return {value for value in values if value}


def tennis_data_name_matches_canonical(source_name: str, canonical_name: str) -> bool:
    """Outcome-blind source-specific identity predicate frozen in amendment 003."""

    source_norm = normalize_market_player_name(source_name)
    canonical_norm = normalize_market_player_name(canonical_name)
    if not source_norm or not canonical_norm:
        return False
    if source_norm == canonical_norm:
        return True

    alias = parse_tennis_data_abbreviation(source_name)
    canonical_tokens = canonical_norm.split()
    if alias is not None:
        for start in _contiguous_positions(canonical_tokens, alias.surname_tokens):
            prefix = canonical_tokens[:start]
            if alias.initials in _prefix_initial_candidates(prefix):
                return True
        return False

    source_tokens = source_norm.split()
    return len(source_tokens) == 2 and canonical_tokens == list(reversed(source_tokens))


def tennis_data_orientation(
    source_name_1: str,
    source_name_2: str,
    canonical_name_a: str,
    canonical_name_b: str,
) -> tuple[int, ...]:
    """Return unique candidate orientations: 1 means 1->A/2->B, -1 means reversed."""

    orientations: list[int] = []
    if tennis_data_name_matches_canonical(source_name_1, canonical_name_a) and (
        tennis_data_name_matches_canonical(source_name_2, canonical_name_b)
    ):
        orientations.append(1)
    if tennis_data_name_matches_canonical(source_name_1, canonical_name_b) and (
        tennis_data_name_matches_canonical(source_name_2, canonical_name_a)
    ):
        orientations.append(-1)
    return tuple(orientations)
