from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}: {old[:80]!r}")
    target.write_text(text.replace(old, new, 1))


def append_once(path: str, marker: str, block: str) -> None:
    target = ROOT / path
    text = target.read_text()
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + block.strip() + "\n")


# ---------------------------------------------------------------------------
# 1. Preserve historical canonical Player A/B orientation in live identity.
# ---------------------------------------------------------------------------
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live_identity.py",
    '_VERSION = "pattern-confirm-identity-v2"',
    '_VERSION = "pattern-confirm-identity-v3"',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live_identity.py",
    '''    if canonical_a == canonical_b:\n        raise ValueError("canonical player IDs must differ")\n\n    unsigned: dict[str, object] = {''',
    '''    if canonical_a == canonical_b:\n        raise ValueError("canonical player IDs must differ")\n\n    # Historical training orients Player A/B by sorted canonical player ID.\n    # Provider home/away is transport metadata only and must never redefine the\n    # fitted model's side convention. Keep every side-specific field attached\n    # to the same real player while restoring the historical canonical order.\n    provider_sides = [\n        (\n            canonical_a,\n            market_a,\n            sportradar_event.player_a_sportradar_id,\n            sportradar_event.player_a_sportradar_name,\n        ),\n        (\n            canonical_b,\n            market_b,\n            sportradar_event.player_b_sportradar_id,\n            sportradar_event.player_b_sportradar_name,\n        ),\n    ]\n    provider_sides.sort(key=lambda item: item[0])\n    canonical_a, market_a, sportradar_a_id, sportradar_a_name = provider_sides[0]\n    canonical_b, market_b, sportradar_b_id, sportradar_b_name = provider_sides[1]\n\n    unsigned: dict[str, object] = {''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live_identity.py",
    '''        "player_a_sportradar_id": sportradar_event.player_a_sportradar_id,\n        "player_b_sportradar_id": sportradar_event.player_b_sportradar_id,\n        "player_a_canonical_id": canonical_a,\n        "player_b_canonical_id": canonical_b,\n        "player_a_sportradar_name": sportradar_event.player_a_sportradar_name,\n        "player_b_sportradar_name": sportradar_event.player_b_sportradar_name,''',
    '''        "player_a_sportradar_id": sportradar_a_id,\n        "player_b_sportradar_id": sportradar_b_id,\n        "player_a_canonical_id": canonical_a,\n        "player_b_canonical_id": canonical_b,\n        "player_a_sportradar_name": sportradar_a_name,\n        "player_b_sportradar_name": sportradar_b_name,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live_identity.py",
    '''    if mapping.player_a_canonical_id == mapping.player_b_canonical_id:\n        raise ValueError("identity mapping canonical player IDs must differ")\n    _aware_time(mapping.created_at, field="created_at")''',
    '''    if mapping.player_a_canonical_id == mapping.player_b_canonical_id:\n        raise ValueError("identity mapping canonical player IDs must differ")\n    if mapping.player_a_canonical_id >= mapping.player_b_canonical_id:\n        raise ValueError("identity mapping does not preserve historical canonical A/B order")\n    _aware_time(mapping.created_at, field="created_at")''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live_identity.py",
    '''    if mapping.player_a_sportradar_id != event.player_a_sportradar_id:\n        raise ValueError("identity mapping player A does not match Sportradar home competitor")\n    if mapping.player_b_sportradar_id != event.player_b_sportradar_id:\n        raise ValueError("identity mapping player B does not match Sportradar away competitor")''',
    '''    event_names = {\n        event.player_a_sportradar_id: event.player_a_sportradar_name,\n        event.player_b_sportradar_id: event.player_b_sportradar_name,\n    }\n    mapped_names = {\n        mapping.player_a_sportradar_id: mapping.player_a_sportradar_name,\n        mapping.player_b_sportradar_id: mapping.player_b_sportradar_name,\n    }\n    if set(mapped_names) != set(event_names):\n        raise ValueError("identity mapping competitors do not match Sportradar event")\n    for competitor_id, mapped_name in mapped_names.items():\n        if mapped_name != event_names[competitor_id]:\n            raise ValueError("identity mapping competitor name does not match Sportradar event")''',
)

# Target state must attach provider attributes to canonical sides by competitor ID.
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_state.py",
    '''    competitors = _qualified_competitors(sport_event)\n    home = competitors["home"]\n    away = competitors["away"]\n    if _required_text(home, "id") != identity_mapping.player_a_sportradar_id:\n        raise ValueError("target home competitor does not match identity mapping")\n    if _required_text(away, "id") != identity_mapping.player_b_sportradar_id:\n        raise ValueError("target away competitor does not match identity mapping")''',
    '''    competitors = _qualified_competitors(sport_event)\n    by_id = {_required_text(item, "id"): item for item in competitors.values()}\n    expected_ids = {\n        identity_mapping.player_a_sportradar_id,\n        identity_mapping.player_b_sportradar_id,\n    }\n    if set(by_id) != expected_ids:\n        raise ValueError("target competitors do not match identity mapping")\n    player_a_competitor = by_id[identity_mapping.player_a_sportradar_id]\n    player_b_competitor = by_id[identity_mapping.player_b_sportradar_id]''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_state.py",
    '''        seed_a=_positive_int(home.get("seed"), field="home seed"),\n        seed_b=_positive_int(away.get("seed"), field="away seed"),''',
    '''        seed_a=_positive_int(player_a_competitor.get("seed"), field="player A seed"),\n        seed_b=_positive_int(player_b_competitor.get("seed"), field="player B seed"),''',
)

# ---------------------------------------------------------------------------
# 2. Fixed looks use a resolved chronological prefix and expose membership.
# ---------------------------------------------------------------------------
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''class LookResult:\n    look_index: int\n    n: int\n    z: float''',
    '''class LookResult:\n    look_index: int\n    n: int\n    match_ids: tuple[str, ...]\n    input_sha256: str\n    z: float''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''    subset = records[:look_n]\n    y = [bool(outcomes[row.match_id].outcome_a) for row in subset]''',
    '''    subset = records[:look_n]\n    look_input = {\n        "hypothesis_id": hypothesis.hypothesis_id,\n        "look_index": look_index + 1,\n        "records": [\n            {\n                "match_id": row.match_id,\n                "record_sha256": row.record_sha256,\n                "outcome_a": outcomes[row.match_id].outcome_a,\n                "retirement": outcomes[row.match_id].retirement,\n                "walkover": outcomes[row.match_id].walkover,\n            }\n            for row in subset\n        ],\n    }\n    input_sha256 = _sha256_bytes(_canonical_json(look_input))\n    y = [bool(outcomes[row.match_id].outcome_a) for row in subset]''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''        look_index=look_index + 1,\n        n=look_n,\n        z=float(z),''',
    '''        look_index=look_index + 1,\n        n=look_n,\n        match_ids=tuple(row.match_id for row in subset),\n        input_sha256=input_sha256,\n        z=float(z),''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''def evaluate_hypothesis(\n    records: list[ProspectiveRecord],\n    outcomes: dict[str, SettledOutcome],\n    hypothesis: PatternHypothesis,\n) -> HypothesisReport:\n    chronological = sorted(\n        [\n            record\n            for record in records\n            if hypothesis.hypothesis_id in record.matched_hypotheses\n            and record.match_id in outcomes\n        ],\n        key=lambda record: (\n            _parse_aware_datetime(record.scheduled_start),\n            record.match_id,\n        ),\n    )\n    retirement_n = sum(outcomes[row.match_id].retirement for row in chronological)\n    walkover_n = sum(outcomes[row.match_id].walkover for row in chronological)\n    eligible = [\n        row\n        for row in chronological\n        if not outcomes[row.match_id].retirement\n        and not outcomes[row.match_id].walkover\n        and outcomes[row.match_id].outcome_a is not None\n    ]''',
    '''def evaluate_hypothesis(\n    records: list[ProspectiveRecord],\n    outcomes: dict[str, SettledOutcome],\n    hypothesis: PatternHypothesis,\n    *,\n    terminal_exclusions: set[str] | None = None,\n) -> HypothesisReport:\n    terminal_exclusions = terminal_exclusions or set()\n    chronological = sorted(\n        [\n            record\n            for record in records\n            if hypothesis.hypothesis_id in record.matched_hypotheses\n        ],\n        key=lambda record: (\n            _parse_aware_datetime(record.scheduled_start),\n            record.match_id,\n        ),\n    )\n\n    # Never skip an unresolved earlier qualifying match and pull a later match\n    # into an interim look. Explicit terminal exclusions are resolved but do not\n    # contribute N; otherwise the first missing settlement closes the prefix.\n    resolved_prefix: list[ProspectiveRecord] = []\n    for record in chronological:\n        if record.match_id in terminal_exclusions:\n            resolved_prefix.append(record)\n            continue\n        if record.match_id not in outcomes:\n            break\n        resolved_prefix.append(record)\n\n    retirement_n = sum(\n        outcomes[row.match_id].retirement\n        for row in resolved_prefix\n        if row.match_id in outcomes\n    )\n    walkover_n = sum(\n        outcomes[row.match_id].walkover\n        for row in resolved_prefix\n        if row.match_id in outcomes\n    )\n    eligible = [\n        row\n        for row in resolved_prefix\n        if row.match_id in outcomes\n        and not outcomes[row.match_id].retirement\n        and not outcomes[row.match_id].walkover\n        and outcomes[row.match_id].outcome_a is not None\n    ]''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''def evaluate_family(\n    records: list[ProspectiveRecord],\n    outcomes: dict[str, SettledOutcome],\n    *,\n    fit: FrozenMarketCoreFit,\n    ledger_sha256: str,\n    outcomes_sha256: str,\n) -> ConfirmationReport:''',
    '''def evaluate_family(\n    records: list[ProspectiveRecord],\n    outcomes: dict[str, SettledOutcome],\n    *,\n    fit: FrozenMarketCoreFit,\n    ledger_sha256: str,\n    outcomes_sha256: str,\n    terminal_exclusions: set[str] | None = None,\n) -> ConfirmationReport:''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm.py",
    '''    reports = tuple(\n        evaluate_hypothesis(records, outcomes, hypothesis) for hypothesis in HYPOTHESES\n    )''',
    '''    reports = tuple(\n        evaluate_hypothesis(\n            records,\n            outcomes,\n            hypothesis,\n            terminal_exclusions=terminal_exclusions,\n        )\n        for hypothesis in HYPOTHESES\n    )''',
)

# ---------------------------------------------------------------------------
# 3. Live records canonicalize provider price sides and enforce event uniqueness.
# ---------------------------------------------------------------------------
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '_VERSION = "pattern-confirm-live-v4"',
    '_VERSION = "pattern-confirm-live-v5"',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''def _devig_probability(odds_a: float, odds_b: float) -> float:\n    q_a = 1.0 / odds_a\n    q_b = 1.0 / odds_b\n    return q_a / (q_a + q_b)\n\n\ndef _require_frozen_model_contract''',
    '''def _devig_probability(odds_a: float, odds_b: float) -> float:\n    q_a = 1.0 / odds_a\n    q_b = 1.0 / odds_b\n    return q_a / (q_a + q_b)\n\n\ndef _require_unique_live_events(records: list[LiveProspectiveRecord]) -> None:\n    for field in ("match_id", "market_event_id", "sportradar_event_id"):\n        values = [str(getattr(record, field)) for record in records]\n        if len(values) != len(set(values)):\n            raise ValueError(f"live prospective ledger contains duplicate {field} values")\n\n\ndef _require_frozen_model_contract''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    market_event_id = _required_text(raw, "market_event_id")\n    player_a_market_name = _required_text(raw, "player_a_market_name")\n    player_b_market_name = _required_text(raw, "player_b_market_name")\n    if market_event_id != identity_mapping.market_event_id:\n        raise ValueError("market event does not match verified identity mapping")\n    if player_a_market_name != identity_mapping.player_a_market_name:\n        raise ValueError("market player A orientation does not match identity mapping")\n    if player_b_market_name != identity_mapping.player_b_market_name:\n        raise ValueError("market player B orientation does not match identity mapping")''',
    '''    market_event_id = _required_text(raw, "market_event_id")\n    raw_market_a_name = _required_text(raw, "player_a_market_name")\n    raw_market_b_name = _required_text(raw, "player_b_market_name")\n    if market_event_id != identity_mapping.market_event_id:\n        raise ValueError("market event does not match verified identity mapping")\n\n    raw_odds_a = _decimal_odds(raw, "decimal_odds_a")\n    raw_odds_b = _decimal_odds(raw, "decimal_odds_b")\n    canonical_names = (\n        identity_mapping.player_a_market_name,\n        identity_mapping.player_b_market_name,\n    )\n    raw_names = (raw_market_a_name, raw_market_b_name)\n    if raw_names == canonical_names:\n        odds_a, odds_b = raw_odds_a, raw_odds_b\n    elif raw_names == canonical_names[::-1]:\n        odds_a, odds_b = raw_odds_b, raw_odds_a\n    else:\n        raise ValueError("market competitor names do not match verified identity mapping")\n    player_a_market_name, player_b_market_name = canonical_names''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    odds_a = _decimal_odds(raw, "decimal_odds_a")\n    odds_b = _decimal_odds(raw, "decimal_odds_b")\n    market_probability = _devig_probability(odds_a, odds_b)''',
    '''    market_probability = _devig_probability(odds_a, odds_b)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    ids = [record.match_id for record in [*existing, *additions]]\n    if len(ids) != len(set(ids)):\n        raise ValueError("live prospective ledger contains duplicate match_id values")\n    return sorted(\n        [*existing, *additions],''',
    '''    combined = [*existing, *additions]\n    _require_unique_live_events(combined)\n    return sorted(\n        combined,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    _require_frozen_model_contract(fit, profile_artifact, core_artifact)\n    eligible_records: list[ProspectiveRecord] = []\n    eligible_outcomes: dict[str, SettledOutcome] = {}\n    timing_exclusions: list[TimingExclusion] = []\n    for record in records:''',
    '''    _require_frozen_model_contract(fit, profile_artifact, core_artifact)\n    _require_unique_live_events(records)\n    evaluation_records = [record.core_record for record in records]\n    eligible_outcomes: dict[str, SettledOutcome] = {}\n    terminal_exclusions: set[str] = set()\n    timing_exclusions: list[TimingExclusion] = []\n    for record in records:''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''            timing_exclusions.append(\n                TimingExclusion(\n                    match_id=record.match_id,\n                    sportradar_event_id=record.sportradar_event_id,\n                    provider_snapshot_at=record.provider_snapshot_at,\n                    prediction_committed_at=record.prediction_committed_at,\n                    actual_start=settlement.actual_start,\n                    reason=reason,\n                )\n            )\n            continue\n        eligible_records.append(record.core_record)\n        eligible_outcomes[record.match_id] = SettledOutcome(''',
    '''            timing_exclusions.append(\n                TimingExclusion(\n                    match_id=record.match_id,\n                    sportradar_event_id=record.sportradar_event_id,\n                    provider_snapshot_at=record.provider_snapshot_at,\n                    prediction_committed_at=record.prediction_committed_at,\n                    actual_start=settlement.actual_start,\n                    reason=reason,\n                )\n            )\n            terminal_exclusions.add(record.match_id)\n            continue\n        eligible_outcomes[record.match_id] = SettledOutcome(''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    core_report = evaluate_family(\n        eligible_records,\n        eligible_outcomes,\n        fit=fit,\n        ledger_sha256=ledger_sha256,\n        outcomes_sha256=settlement_sha256,\n    )''',
    '''    core_report = evaluate_family(\n        evaluation_records,\n        eligible_outcomes,\n        fit=fit,\n        ledger_sha256=ledger_sha256,\n        outcomes_sha256=settlement_sha256,\n        terminal_exclusions=terminal_exclusions,\n    )''',
)

# Persist completed look membership and reject silent sample substitution.
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''def _load_contracts(\n    fit_path: Path,''',
    '''def _completed_looks(report_payload: dict[str, object]) -> dict[str, list[dict[str, object]]]:\n    core = report_payload.get("core_confirmation")\n    if not isinstance(core, dict):\n        raise ValueError("look-state is missing core_confirmation")\n    hypotheses = core.get("hypotheses")\n    if not isinstance(hypotheses, list):\n        raise ValueError("look-state is missing hypothesis reports")\n    result: dict[str, list[dict[str, object]]] = {}\n    for raw in hypotheses:\n        if not isinstance(raw, dict):\n            raise ValueError("look-state hypothesis report must be an object")\n        hypothesis_id = str(raw.get("hypothesis_id", ""))\n        looks = raw.get("completed_looks")\n        if not hypothesis_id or not isinstance(looks, list):\n            raise ValueError("look-state hypothesis report is malformed")\n        if not all(isinstance(item, dict) for item in looks):\n            raise ValueError("look-state completed look must be an object")\n        result[hypothesis_id] = list(looks)\n    return result\n\n\ndef assert_completed_looks_stable(\n    previous: dict[str, object],\n    current: dict[str, object],\n) -> None:\n    for field in (\n        "experiment_id",\n        "profile_model_sha256",\n        "core_model_sha256",\n        "market_core_fit_sha256",\n    ):\n        if previous.get(field) != current.get(field):\n            raise ValueError(f"look-state frozen field changed: {field}")\n    previous_looks = _completed_looks(previous)\n    current_looks = _completed_looks(current)\n    if set(previous_looks) != set(current_looks):\n        raise ValueError("look-state hypothesis family changed")\n    for hypothesis_id, sealed in previous_looks.items():\n        now = current_looks[hypothesis_id]\n        if len(now) < len(sealed):\n            raise ValueError("a previously completed look disappeared")\n        for index, old_look in enumerate(sealed):\n            if old_look != now[index]:\n                raise ValueError(\n                    f"completed look membership/result changed for {hypothesis_id} look {index + 1}"\n                )\n\n\ndef _write_json_atomic(path: Path, payload: dict[str, object]) -> None:\n    path.parent.mkdir(parents=True, exist_ok=True)\n    temporary = path.with_suffix(path.suffix + ".tmp")\n    temporary.write_text(\n        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\\n"\n    )\n    temporary.replace(path)\n\n\ndef _load_contracts(\n    fit_path: Path,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''    evaluate.add_argument("--ledger", required=True, type=Path)\n    evaluate.add_argument("--settlements", required=True, type=Path)\n    evaluate.add_argument("--output", required=True, type=Path)''',
    '''    evaluate.add_argument("--ledger", required=True, type=Path)\n    evaluate.add_argument("--settlements", required=True, type=Path)\n    evaluate.add_argument("--look-state", required=True, type=Path)\n    evaluate.add_argument("--output", required=True, type=Path)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''        args.output.write_text(\n            json.dumps(asdict(report), indent=2, sort_keys=True, allow_nan=False) + "\\n"\n        )\n        return''',
    '''        payload = asdict(report)\n        if args.look_state.exists():\n            previous = json.loads(args.look_state.read_text())\n            if not isinstance(previous, dict):\n                raise ValueError("look-state must be a JSON object")\n            assert_completed_looks_stable(previous, payload)\n        _write_json_atomic(args.look_state, payload)\n        _write_json_atomic(args.output, payload)\n        return''',
)

# ---------------------------------------------------------------------------
# 4. Bind frozen base history to every feature-bearing canonical field.
# ---------------------------------------------------------------------------
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    'from datetime import date',
    'from dataclasses import asdict\nfrom datetime import date',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''HISTORY_SOURCE_ID = "CANONICAL_2000_2025_PLUS_SPORTRADAR_TENNIS_V3_STATE_V1"\nHISTORY_SOURCE_CONTRACT = "pattern-confirm-history-source-v2"\n_BASE_END = date(2025, 12, 31)''',
    '''HISTORY_SOURCE_ID = "CANONICAL_2000_2025_PLUS_SPORTRADAR_TENNIS_V3_STATE_V1"\nHISTORY_SOURCE_CONTRACT = "pattern-confirm-history-source-v3"\nFROZEN_BASE_HISTORY_CONTENT_SHA256 = "__FROZEN_BASE_HISTORY_CONTENT_SHA256__"\n_BASE_END = date(2025, 12, 31)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''    base_training_rows_sha256: str,\n    state_capture_sha256: str,''',
    '''    base_training_rows_sha256: str,\n    base_history_content_sha256: str,\n    state_capture_sha256: str,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''                "base_training_rows_sha256": base_training_rows_sha256,\n                "state_capture_sha256": state_capture_sha256,''',
    '''                "base_training_rows_sha256": base_training_rows_sha256,\n                "base_history_content_sha256": base_history_content_sha256,\n                "state_capture_sha256": state_capture_sha256,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''def verified_frozen_base_history(\n    base_history: list[HistoricalMatch],\n    *,\n    profile_artifact: ProfileProductionArtifact,\n    core_artifact: CoreProductionArtifact,\n) -> list[HistoricalMatch]:''',
    '''def training_content_hash(matches: list[HistoricalMatch]) -> str:\n    rows: list[dict[str, object]] = []\n    for match in matches:\n        pre_match = asdict(match.pre_match)\n        pre_match["event_date"] = match.pre_match.event_date.isoformat()\n        rows.append(\n            {\n                "pre_match": pre_match,\n                "outcome": asdict(match.outcome),\n                "stats": None if match.stats is None else asdict(match.stats),\n            }\n        )\n    rows.sort(\n        key=lambda row: (\n            str(row["pre_match"]["event_date"]),\n            int(row["pre_match"]["source_order"]),\n            str(row["pre_match"]["match_id"]),\n        )\n    )\n    return _sha256(_canonical_json(rows))\n\n\ndef verified_frozen_base_history(\n    base_history: list[HistoricalMatch],\n    *,\n    profile_artifact: ProfileProductionArtifact,\n    core_artifact: CoreProductionArtifact,\n    expected_content_sha256: str | None = None,\n) -> list[HistoricalMatch]:''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''    if training_population_hash(eligible) != profile_artifact.training_rows_sha256:\n        raise ValueError("frozen base history does not reproduce training-row hash")\n    eligible.sort(''',
    '''    if training_population_hash(eligible) != profile_artifact.training_rows_sha256:\n        raise ValueError("frozen base history does not reproduce training-row hash")\n    if expected_content_sha256 is not None:\n        actual_content_sha256 = training_content_hash(eligible)\n        if actual_content_sha256 != expected_content_sha256:\n            raise ValueError("frozen base history does not reproduce full content hash")\n    eligible.sort(''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''    core_artifact: CoreProductionArtifact,\n) -> ProspectiveStateArtifact:\n    base = verified_frozen_base_history(\n        base_history,\n        profile_artifact=profile_artifact,\n        core_artifact=core_artifact,\n    )''',
    '''    core_artifact: CoreProductionArtifact,\n    expected_base_history_content_sha256: str | None = None,\n) -> ProspectiveStateArtifact:\n    base = verified_frozen_base_history(\n        base_history,\n        profile_artifact=profile_artifact,\n        core_artifact=core_artifact,\n        expected_content_sha256=expected_base_history_content_sha256,\n    )\n    base_history_content_sha256 = training_content_hash(base)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_pipeline.py",
    '''        base_training_rows_sha256=profile_artifact.training_rows_sha256,\n        state_capture_sha256=state_capture.artifact_sha256,''',
    '''        base_training_rows_sha256=profile_artifact.training_rows_sha256,\n        base_history_content_sha256=base_history_content_sha256,\n        state_capture_sha256=state_capture.artifact_sha256,''',
)

# Source packages carry and verify the complete frozen base-history identity.
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''    HISTORY_SOURCE_ID,\n    build_sportradar_prospective_state,\n    history_source_sha256,''',
    '''    FROZEN_BASE_HISTORY_CONTENT_SHA256,\n    HISTORY_SOURCE_ID,\n    build_sportradar_prospective_state,\n    history_source_sha256,\n    training_content_hash,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '_VERSION = "pattern-confirm-sportradar-source-package-v2"',
    '_VERSION = "pattern-confirm-sportradar-source-package-v3"',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''    prospective_state_sha256: str\n    selected_season_count: int''',
    '''    prospective_state_sha256: str\n    base_history_content_sha256: str\n    selected_season_count: int''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''    prospective_state = build_sportradar_prospective_state(\n        base_history=base_history,''',
    '''    expected_base_content = (\n        FROZEN_BASE_HISTORY_CONTENT_SHA256\n        if (\n            profile_artifact.artifact_sha256\n            == "cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351"\n            and core_artifact.artifact_sha256\n            == "5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7"\n        )\n        else None\n    )\n    prospective_state = build_sportradar_prospective_state(\n        base_history=base_history,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''        profile_artifact=profile_artifact,\n        core_artifact=core_artifact,\n    )\n    prospective_payload = prospective_state_as_dict(prospective_state)''',
    '''        profile_artifact=profile_artifact,\n        core_artifact=core_artifact,\n        expected_base_history_content_sha256=expected_base_content,\n    )\n    base_eligible = [\n        match\n        for match in base_history\n        if match.pre_match.tour == "ATP"\n        and not match.outcome.walkover\n        and not match.outcome.retirement\n    ]\n    base_history_content_sha256 = training_content_hash(base_eligible)\n    prospective_payload = prospective_state_as_dict(prospective_state)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''        "prospective_state_sha256": prospective_state.artifact_sha256,\n        "selected_season_count": state_capture.selected_season_count,''',
    '''        "prospective_state_sha256": prospective_state.artifact_sha256,\n        "base_history_content_sha256": base_history_content_sha256,\n        "selected_season_count": state_capture.selected_season_count,''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''    if profile_artifact.canonical_manifest_sha256 != core_artifact.canonical_manifest_sha256:\n        raise ValueError("source package Profile/Core canonical manifest hashes differ")\n\n    sealed_crosswalk = verify_crosswalk(crosswalk_payload)''',
    '''    if profile_artifact.canonical_manifest_sha256 != core_artifact.canonical_manifest_sha256:\n        raise ValueError("source package Profile/Core canonical manifest hashes differ")\n    if len(package.base_history_content_sha256) != 64 or any(\n        char not in "0123456789abcdef" for char in package.base_history_content_sha256\n    ):\n        raise ValueError("source package base-history content hash is invalid")\n    if (\n        profile_artifact.artifact_sha256\n        == "cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351"\n        and core_artifact.artifact_sha256\n        == "5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7"\n        and package.base_history_content_sha256 != FROZEN_BASE_HISTORY_CONTENT_SHA256\n    ):\n        raise ValueError("source package does not bind the frozen base-history content")\n\n    sealed_crosswalk = verify_crosswalk(crosswalk_payload)''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_sportradar_source_package.py",
    '''        base_training_rows_sha256=profile_artifact.training_rows_sha256,\n        state_capture_sha256=capture.artifact_sha256,''',
    '''        base_training_rows_sha256=profile_artifact.training_rows_sha256,\n        base_history_content_sha256=package.base_history_content_sha256,\n        state_capture_sha256=capture.artifact_sha256,''',
)

# ---------------------------------------------------------------------------
# Regression tests for the reproduced defects.
# ---------------------------------------------------------------------------
replace_once(
    "tests/test_pattern_confirm_live.py",
    '''def _source_package_payload(*, captured_at: datetime | None = None) -> dict[str, object]:''',
    '''def _source_package_payload(\n    *,\n    captured_at: datetime | None = None,\n    match_id: str = "future-1",\n) -> dict[str, object]:''',
)
replace_once(
    "tests/test_pattern_confirm_live.py",
    '''    package = build_live_source_package(\n        match_id="future-1",''',
    '''    package = build_live_source_package(\n        match_id=match_id,''',
)
replace_once(
    "tests/test_pattern_confirm_live.py",
    '''        ({"player_a_market_name": "Taylor Fritz"}, "player A orientation"),''',
    '''        ({"player_a_market_name": "Taylor Fritz"}, "competitor names"),''',
)
append_once(
    "tests/test_pattern_confirm.py",
    "test_unsettled_earlier_match_blocks_fixed_look_membership",
    '''def test_unsettled_earlier_match_blocks_fixed_look_membership() -> None:\n    hypothesis = HYPOTHESES[0]\n    look_n = hypothesis.look_ns[0]\n    records = [\n        _prospective_record(\n            index,\n            hypothesis_id=hypothesis.hypothesis_id,\n            probability=0.60,\n        )\n        for index in range(look_n + 1)\n    ]\n    outcomes = {\n        row.match_id: SettledOutcome(\n            match_id=row.match_id,\n            outcome_a=index < 235,\n            retirement=False,\n            walkover=False,\n        )\n        for index, row in enumerate(records)\n        if index != 0\n    }\n\n    report = evaluate_hypothesis(records, outcomes, hypothesis)\n    assert report.status == "ACCUMULATING"\n    assert report.available_qualifying_n == 0\n    assert report.completed_looks == ()\n\n    outcomes[records[0].match_id] = SettledOutcome(\n        match_id=records[0].match_id,\n        outcome_a=True,\n        retirement=False,\n        walkover=False,\n    )\n    report = evaluate_hypothesis(records, outcomes, hypothesis)\n    assert len(report.completed_looks) == 1\n    look = report.completed_looks[0]\n    assert look.match_ids == tuple(row.match_id for row in records[:look_n])\n    assert len(look.input_sha256) == 64''',
)
append_once(
    "tests/test_pattern_confirm_live.py",
    "test_market_side_swap_is_reoriented_to_canonical_player_a",
    '''def test_market_side_swap_is_reoriented_to_canonical_player_a() -> None:\n    canonical = _build()\n    swapped = _build(\n        _raw(\n            player_a_market_name="Taylor Fritz",\n            player_b_market_name="Tommy Paul",\n            decimal_odds_a=2.10,\n            decimal_odds_b=1.80,\n        )\n    )\n    assert swapped.player_a_id == canonical.player_a_id\n    assert swapped.player_b_id == canonical.player_b_id\n    assert swapped.market_probability_a == pytest.approx(canonical.market_probability_a)\n    assert swapped.decimal_odds_a == canonical.decimal_odds_a\n    assert swapped.decimal_odds_b == canonical.decimal_odds_b\n\n\ndef test_duplicate_provider_event_is_rejected_even_with_new_internal_id() -> None:\n    first = _build()\n    second_package = _source_package_payload(match_id="future-2")\n    mapping = _mapping()\n    with pytest.raises(ValueError, match="duplicate (market_event_id|sportradar_event_id)"):\n        append_live_rows(\n            existing_rows=[live_record_as_dict(first)],\n            new_rows=[_raw(match_id="future-2")],\n            identity_mappings={mapping.market_event_id: mapping},\n            source_packages={\n                "future-1": _source_package_payload(),\n                "future-2": second_package,\n            },\n            crosswalk_payload=_crosswalk_payload(),\n            fit=_fit(),\n            profile_artifact=_profile(),\n            core_artifact=_core(),\n        )''',
)
append_once(
    "tests/test_pattern_confirm_live_identity.py",
    "test_identity_mapping_restores_historical_canonical_order_across_home_away",
    '''def test_identity_mapping_restores_historical_canonical_order_across_home_away() -> None:\n    event = parse_sportradar_prematch_event(_summary())\n    mapping = build_identity_mapping(\n        market_event_id="odds-event-reversed",\n        market_player_a_name="Paul, Tommy",\n        market_player_b_name="Fritz, Taylor",\n        player_a_canonical_id="atp:id:999",\n        player_b_canonical_id="atp:id:111",\n        sportradar_event=event,\n        method="EXPLICIT_CROSSWALK",\n        created_at="2026-09-12T15:00:00+00:00",\n    )\n    assert mapping.player_a_canonical_id == "atp:id:111"\n    assert mapping.player_b_canonical_id == "atp:id:999"\n    assert mapping.player_a_sportradar_id == "sr:competitor:22"\n    assert mapping.player_b_sportradar_id == "sr:competitor:11"\n    assert mapping.player_a_market_name == "Fritz, Taylor"\n    validate_mapping_against_event(mapping, event)''',
)
replace_once(
    "tests/test_pattern_confirm_live_identity.py",
    '''def test_mapping_must_still_match_event_and_orientation() -> None:\n    mapping = _mapping()\n    validate_mapping_against_event(mapping, parse_sportradar_prematch_event(_summary()))\n\n    swapped = parse_sportradar_prematch_event(\n        _summary(\n            home_id="sr:competitor:22",\n            away_id="sr:competitor:11",\n            home_name="Fritz, Taylor",\n            away_name="Paul, Tommy",\n        )\n    )\n    with pytest.raises(ValueError, match="player A"):\n        validate_mapping_against_event(mapping, swapped)''',
    '''def test_mapping_matches_stable_event_competitors_independent_of_home_away() -> None:\n    mapping = _mapping()\n    validate_mapping_against_event(mapping, parse_sportradar_prematch_event(_summary()))\n\n    swapped = parse_sportradar_prematch_event(\n        _summary(\n            home_id="sr:competitor:22",\n            away_id="sr:competitor:11",\n            home_name="Fritz, Taylor",\n            away_name="Paul, Tommy",\n        )\n    )\n    validate_mapping_against_event(mapping, swapped)''',
)
# Keep the identity test fixtures canonically ordered unless the test explicitly reverses them.
for old, new in [
    ('player_a_canonical_id="tommy_paul"', 'player_a_canonical_id="atp:id:111"'),
    ('player_b_canonical_id="taylor_fritz"', 'player_b_canonical_id="atp:id:222"'),
    ('player_a_canonical_id="taylor_fritz"', 'player_a_canonical_id="atp:id:222"'),
    ('player_b_canonical_id="tommy_paul"', 'player_b_canonical_id="atp:id:111"'),
    ('assert mapping.player_a_canonical_id == "tommy_paul"', 'assert mapping.player_a_canonical_id == "atp:id:111"'),
    ('assert mapping.player_b_canonical_id == "taylor_fritz"', 'assert mapping.player_b_canonical_id == "atp:id:222"'),
]:
    target = ROOT / "tests/test_pattern_confirm_live_identity.py"
    text = target.read_text()
    if old in text:
        target.write_text(text.replace(old, new))

replace_once(
    "tests/test_pattern_confirm_sportradar_pipeline.py",
    '''    build_sportradar_prospective_state,\n    training_population_hash,\n    verified_frozen_base_history,''',
    '''    build_sportradar_prospective_state,\n    training_content_hash,\n    training_population_hash,\n    verified_frozen_base_history,''',
)
append_once(
    "tests/test_pattern_confirm_sportradar_pipeline.py",
    "test_frozen_base_full_content_hash_rejects_feature_bearing_mutation",
    '''def test_frozen_base_full_content_hash_rejects_feature_bearing_mutation() -> None:\n    base = _base()\n    profile, core = _toy_models(base)\n    expected = training_content_hash(base)\n    assert (\n        verified_frozen_base_history(\n            base,\n            profile_artifact=profile,\n            core_artifact=core,\n            expected_content_sha256=expected,\n        )\n        == base\n    )\n    assert base[0].stats is not None\n    changed = [\n        replace(base[0], stats=replace(base[0].stats, duration_minutes=9999)),\n        base[1],\n    ]\n    assert training_population_hash(changed) == training_population_hash(base)\n    with pytest.raises(ValueError, match="full content hash"):\n        verified_frozen_base_history(\n            changed,\n            profile_artifact=profile,\n            core_artifact=core,\n            expected_content_sha256=expected,\n        )''',
)

# Pre-result amendment: science unchanged; implementation boundaries repaired at N=0.
amendment = ROOT / "research/installment_01/pattern_confirm_001_preresult_amendment_010.md"
amendment.write_text('''# PATTERN-CONFIRM-001 Pre-result Amendment 010 — Prospective correctness repair\n\nStatus: **REGISTERED AT PROSPECTIVE N = 0 BEFORE ANY ELIGIBLE POST-CUTOFF OUTCOME IS INSPECTED**\n\nAn independent read-only repository review of `main` at `934767ff83e4745dc53c7b24d2e4168b2441055a` reproduced four implementation defects in the prospective path. This amendment repairs execution so that it matches the already-frozen scientific intent. It does not change either hypothesis, Profile Gap threshold, fixed correction, family alpha, O'Brien-Fleming boundary, look N, provider, five-minute timing rule, model coefficient, or promotion rule.\n\n## 1. Canonical Player A/B orientation\n\nHistorical training defines Player A/B by sorted canonical player ID. Provider home/away is transport metadata only. Every live identity mapping, target feature snapshot, market price, hypothesis membership, correction and settlement is now converted into that same canonical ordering before inference. Display/provider order may be reconstructed only after scientific calculations. The frozen Profile/Core mappings are not retrained.\n\n## 2. Finalized chronological look membership\n\nA fixed look may not skip an unresolved earlier qualifying event and substitute a later settlement. Each hypothesis now advances only through a resolved chronological prefix; explicit terminal exclusions may be passed without contributing N. Every completed look records its exact match IDs and a digest of the sealed records/outcomes. The live evaluator persists a look-state file and rejects any rerun that changes or removes an already completed look.\n\n## 3. Stable provider-event uniqueness\n\nThe live ledger now requires uniqueness of internal match ID, The Odds API market event ID and Sportradar sport-event ID across the complete ledger. The same underlying event cannot enter confirmatory N again under an alias/internal-ID change. Existing ledgers are revalidated under the same rule before evaluation.\n\n## 4. Complete frozen base-history binding\n\nThe old training-population hash remains as a population-identity check, but it is no longer sufficient on its own. A second SHA-256 now covers the complete eligible canonical 2000-2025 historical records consumed by state reconstruction, including feature-bearing pre-match fields and post-match statistics. The production source-package path requires the exact frozen full-content hash and includes it in downstream history provenance.\n\nFrozen base-history content SHA-256: `__FROZEN_BASE_HISTORY_CONTENT_SHA256__`\n\nThe digest is generated from the exact pinned ATP 2000-2025 source after reproducing the frozen 75,112-row population and the existing production champions.\n\n## Evidence accounting\n\nAll prior live/source-package engineering artifacts are superseded before prospective accumulation. No qualifying future outcome was opened to make these repairs and no previously collected confirmatory evidence exists to discard or reclassify. Both hypotheses remain `ACCUMULATING, N=0`.\n''')

print("Applied PATTERN-CONFIRM prospective correctness source/test patch set")
