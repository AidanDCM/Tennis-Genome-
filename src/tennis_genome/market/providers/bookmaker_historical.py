from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast

import pandas as pd

from tennis_genome.data.canonical import Tour
from tennis_genome.market.historical_join import normalize_market_player_name

BookmakerSource = Literal["VALUEBETENNIS", "TENNIS_DATA_UK"]
_NEUTRALIZATION_VERSION = "bookmaker-neutralization-v1"
_DEVELOPMENT_END = date(2025, 12, 31)


@dataclass(frozen=True)
class SanitizedBookmakerQuote:
    source_family: BookmakerSource
    source_file: str
    source_file_sha256: str
    source_row_number: int
    source_row_key: str
    match_date: date
    tour: Tour
    neutral_player_1_name: str
    neutral_player_2_name: str
    neutral_player_1_normalized: str
    neutral_player_2_normalized: str
    decimal_odds_1: float | None
    decimal_odds_2: float | None
    quote_valid: bool
    sanitized_row_hash: str

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["match_date"] = self.match_date.isoformat()
        return payload


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tour(value: object) -> Tour:
    text = str(value).strip().upper()
    if text not in {"ATP", "WTA"}:
        raise ValueError(f"invalid bookmaker tour: {value!r}")
    return cast(Tour, text)


def _optional_decimal(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result <= 1.0:
        return None
    return result


def _parse_valuebet_date(value: object) -> date:
    parsed = pd.to_datetime(value, errors="raise", dayfirst=False)
    return parsed.date()


def _parse_tennis_data_date(value: object) -> date:
    parsed = pd.to_datetime(value, errors="raise", dayfirst=True)
    return parsed.date()


def _neutralize(
    *,
    source_family: BookmakerSource,
    source_file: str,
    source_file_sha256: str,
    source_row_number: int,
    source_row_key: str,
    match_date: date,
    tour: Tour,
    name_left: object,
    name_right: object,
    odds_left: object,
    odds_right: object,
) -> SanitizedBookmakerQuote:
    left_name = str(name_left).strip()
    right_name = str(name_right).strip()
    if not left_name or not right_name:
        raise ValueError("bookmaker contestant names must be non-empty")
    left_norm = normalize_market_player_name(left_name)
    right_norm = normalize_market_player_name(right_name)
    if not left_norm or not right_norm or left_norm == right_norm:
        raise ValueError("bookmaker contestant names do not form a valid pair")
    left_odds = _optional_decimal(odds_left)
    right_odds = _optional_decimal(odds_right)

    entries = sorted(
        ((left_norm, left_name, left_odds), (right_norm, right_name, right_odds)),
        key=lambda item: item[0],
    )
    first_norm, first_name, first_odds = entries[0]
    second_norm, second_name, second_odds = entries[1]
    valid = first_odds is not None and second_odds is not None
    payload = {
        "neutralization_version": _NEUTRALIZATION_VERSION,
        "source_family": source_family,
        "source_file": source_file,
        "source_file_sha256": source_file_sha256,
        "source_row_number": int(source_row_number),
        "source_row_key": str(source_row_key),
        "match_date": match_date.isoformat(),
        "tour": tour,
        "neutral_player_1_name": first_name,
        "neutral_player_2_name": second_name,
        "neutral_player_1_normalized": first_norm,
        "neutral_player_2_normalized": second_norm,
        "decimal_odds_1": first_odds,
        "decimal_odds_2": second_odds,
        "quote_valid": valid,
    }
    row_hash = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return SanitizedBookmakerQuote(
        source_family=source_family,
        source_file=source_file,
        source_file_sha256=source_file_sha256,
        source_row_number=int(source_row_number),
        source_row_key=str(source_row_key),
        match_date=match_date,
        tour=tour,
        neutral_player_1_name=first_name,
        neutral_player_2_name=second_name,
        neutral_player_1_normalized=first_norm,
        neutral_player_2_normalized=second_norm,
        decimal_odds_1=first_odds,
        decimal_odds_2=second_odds,
        quote_valid=valid,
        sanitized_row_hash=row_hash,
    )


def load_valuebetennis_quotes(
    path: str | Path,
    *,
    source_file: str | None = None,
    source_file_sha256: str | None = None,
) -> list[SanitizedBookmakerQuote]:
    """Load only outcome-free Valuebetennis identity/date/closing-price columns."""

    file_path = Path(path)
    file_hash = source_file_sha256 or sha256_file(file_path)
    relative = source_file or file_path.name
    allowed = [
        "match_id",
        "date",
        "genre",
        "joueur1",
        "joueur2",
        "cote1_cloture",
        "cote2_cloture",
    ]
    try:
        frame = pd.read_csv(file_path, sep=";", usecols=allowed, encoding="utf-8-sig")
    except ValueError as exc:
        raise ValueError(
            f"Valuebetennis file missing required market columns: {file_path}"
        ) from exc

    quotes: list[SanitizedBookmakerQuote] = []
    for index, row in enumerate(frame.itertuples(index=False), start=2):
        values = row._asdict()
        quotes.append(
            _neutralize(
                source_family="VALUEBETENNIS",
                source_file=relative,
                source_file_sha256=file_hash,
                source_row_number=index,
                source_row_key=str(values["match_id"]),
                match_date=_parse_valuebet_date(values["date"]),
                tour=_tour(values["genre"]),
                name_left=values["joueur1"],
                name_right=values["joueur2"],
                odds_left=values["cote1_cloture"],
                odds_right=values["cote2_cloture"],
            )
        )
    return quotes


def load_tennis_data_quotes(
    path: str | Path,
    *,
    tour: Tour,
    source_file: str | None = None,
    source_file_sha256: str | None = None,
) -> list[SanitizedBookmakerQuote]:
    """Neutralize Tennis-Data Winner/Loser + Pinnacle odds before downstream use."""

    file_path = Path(path)
    file_hash = source_file_sha256 or sha256_file(file_path)
    relative = source_file or file_path.name
    expected_tour = _tour(tour)
    header = pd.read_csv(file_path, nrows=0, encoding="utf-8-sig")
    if expected_tour not in header.columns:
        raise ValueError(
            f"Tennis-Data file tour marker does not match expected {expected_tour}: {file_path}"
        )
    allowed = ["Date", "Winner", "Loser", "PSW", "PSL"]
    try:
        frame = pd.read_csv(file_path, usecols=allowed, encoding="utf-8-sig")
    except ValueError as exc:
        raise ValueError(
            f"Tennis-Data file missing required Pinnacle columns: {file_path}"
        ) from exc

    quotes: list[SanitizedBookmakerQuote] = []
    for index, row in enumerate(frame.itertuples(index=False), start=2):
        values = row._asdict()
        match_date = _parse_tennis_data_date(values["Date"])
        quotes.append(
            _neutralize(
                source_family="TENNIS_DATA_UK",
                source_file=relative,
                source_file_sha256=file_hash,
                source_row_number=index,
                source_row_key=f"{match_date.isoformat()}:{index}",
                match_date=match_date,
                tour=expected_tour,
                name_left=values["Winner"],
                name_right=values["Loser"],
                odds_left=values["PSW"],
                odds_right=values["PSL"],
            )
        )
    return quotes


def reject_post_2025_quotes(quotes: list[SanitizedBookmakerQuote]) -> None:
    if any(quote.match_date > _DEVELOPMENT_END for quote in quotes):
        raise ValueError("confirmatory bookmaker source contains a post-2025 row")
