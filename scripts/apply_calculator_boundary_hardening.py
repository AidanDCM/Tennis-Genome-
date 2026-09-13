from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement, found {count}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1))


# 1) Calculator input invariants: canonical orientation and Profile validity.
replace_once(
    "src/tennis_genome/calculator/types.py",
    '''        if self.player_a_id == self.player_b_id:\n            raise ValueError("player IDs must be distinct")\n        if self.foundational.match_id != self.match_id:\n''',
    '''        if self.player_a_id == self.player_b_id:\n            raise ValueError("player IDs must be distinct")\n        if self.player_a_id >= self.player_b_id:\n            raise ValueError("player IDs must use canonical ascending A/B order")\n        if self.foundational.match_id != self.match_id:\n''',
)
replace_once(
    "src/tennis_genome/calculator/types.py",
    '''        if len(set(self.source_manifest_hashes)) != len(self.source_manifest_hashes):\n            raise ValueError("source manifest hashes must be unique")\n\n        if self.tour == "ATP":\n''',
    '''        if len(set(self.source_manifest_hashes)) != len(self.source_manifest_hashes):\n            raise ValueError("source manifest hashes must be unique")\n        if isinstance(self.best_of, bool) or self.best_of not in (3, 5):\n            raise ValueError("best_of must be integer 3 or 5")\n\n        if self.tour == "ATP":\n''',
)
replace_once(
    "src/tennis_genome/calculator/types.py",
    '''            if pair.player_a.tour != "ATP" or pair.player_b.tour != "ATP":\n                raise ValueError("ATP profile_pair must contain ATP players")\n        elif self.tour == "WTA":\n''',
    '''            if pair.player_a.tour != "ATP" or pair.player_b.tour != "ATP":\n                raise ValueError("ATP profile_pair must contain ATP players")\n            for label, profile in (("Player A", pair.player_a), ("Player B", pair.player_b)):\n                if profile.valid_until is not None and profile.valid_until < profile.valid_from:\n                    raise ValueError(f"{label} Profile validity interval is inverted")\n                if profile.valid_from > pair.event_date:\n                    raise ValueError(f"{label} Profile is not yet valid for the matchup date")\n                if profile.valid_until is not None and pair.event_date > profile.valid_until:\n                    raise ValueError(f"{label} Profile expired before the matchup date")\n        elif self.tour == "WTA":\n''',
)

# 2) JSON ingestion: reject non-finite values and fractional/bool best_of.
replace_once(
    "src/tennis_genome/calculator/io.py",
    '''import json\nimport re\n''',
    '''import json\nimport math\nimport re\n''',
)
replace_once(
    "src/tennis_genome/calculator/io.py",
    '''def _reject_market_or_outcome_input(payload: Mapping[str, object]) -> None:\n    forbidden = sorted(_forbidden_input_keys(payload))\n    if forbidden:\n        raise ValueError(\n            "market/outcome fields are forbidden inside matchup input: "\n            + ", ".join(forbidden)\n        )\n\n\ndef _datetime''',
    '''def _reject_market_or_outcome_input(payload: Mapping[str, object]) -> None:\n    forbidden = sorted(_forbidden_input_keys(payload))\n    if forbidden:\n        raise ValueError(\n            "market/outcome fields are forbidden inside matchup input: "\n            + ", ".join(forbidden)\n        )\n\n\ndef _reject_nonfinite_numbers(value: object, *, path: str = "input") -> None:\n    if isinstance(value, Mapping):\n        for key, nested in value.items():\n            _reject_nonfinite_numbers(nested, path=f"{path}.{key}")\n        return\n    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):\n        for index, nested in enumerate(value):\n            _reject_nonfinite_numbers(nested, path=f"{path}[{index}]")\n        return\n    if isinstance(value, float) and not math.isfinite(value):\n        raise ValueError(f"{path} contains a non-finite numeric value")\n\n\ndef _best_of(value: object) -> int:\n    if isinstance(value, bool) or not isinstance(value, int):\n        raise ValueError("best_of must be integer 3 or 5")\n    if value not in (3, 5):\n        raise ValueError("best_of must be integer 3 or 5")\n    return value\n\n\ndef _datetime''',
)
replace_once(
    "src/tennis_genome/calculator/io.py",
    '''def matchup_input_from_dict(payload: dict[str, object]) -> MatchupInput:\n    _reject_market_or_outcome_input(payload)\n''',
    '''def matchup_input_from_dict(payload: dict[str, object]) -> MatchupInput:\n    _reject_nonfinite_numbers(payload)\n    _reject_market_or_outcome_input(payload)\n''',
)
replace_once(
    "src/tennis_genome/calculator/io.py",
    '''        source_manifest_hashes=tuple(str(value) for value in source_hashes),\n        best_of=int(payload.get("best_of", 3)),\n''',
    '''        source_manifest_hashes=tuple(str(value) for value in source_hashes),\n        best_of=_best_of(payload.get("best_of", 3)),\n''',
)

# Strict JSON output: never emit NaN/Infinity tokens.
replace_once(
    "src/tennis_genome/calculator/cli.py",
    '''    rendered = json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\\n"\n''',
    '''    rendered = json.dumps(\n        result.to_dict(), indent=2, sort_keys=True, allow_nan=False\n    ) + "\\n"\n''',
)

# 3) Production bundle authenticity for in-memory objects.
replace_once(
    "src/tennis_genome/calculator/contract.py",
    '''from __future__ import annotations\n\nfrom pathlib import Path\n''',
    '''from __future__ import annotations\n\nimport hashlib\nimport json\nfrom dataclasses import asdict\nfrom pathlib import Path\n''',
)
replace_once(
    "src/tennis_genome/calculator/contract.py",
    '''def validate_frozen_bundle_contract(bundle: IndependentProductionBundle) -> None:\n    """Fail closed if a self-consistent bundle is not the frozen production contract."""\n\n    if bundle.artifact_sha256 != FROZEN_PRODUCTION_BUNDLE_SHA256:\n''',
    '''def _recomputed_bundle_sha256(bundle: IndependentProductionBundle) -> str:\n    payload = asdict(bundle)\n    payload.pop("artifact_sha256", None)\n    raw = json.dumps(\n        payload,\n        sort_keys=True,\n        separators=(",", ":"),\n        ensure_ascii=False,\n        allow_nan=False,\n    ).encode("utf-8")\n    return hashlib.sha256(raw).hexdigest()\n\n\ndef validate_frozen_bundle_contract(bundle: IndependentProductionBundle) -> None:\n    """Fail closed unless object content itself is the sealed production contract."""\n\n    if _recomputed_bundle_sha256(bundle) != bundle.artifact_sha256:\n        raise ValueError("production bundle semantic digest does not match object content")\n    if bundle.artifact_sha256 != FROZEN_PRODUCTION_BUNDLE_SHA256:\n''',
)

# If an in-memory object claims to be the sealed production bundle, authenticate it.
replace_once(
    "src/tennis_genome/calculator/engine.py",
    '''        if bundle.model_version != MODEL_VERSION:\n            raise ValueError("unexpected independent production model version")\n''',
    '''        from .contract import FROZEN_PRODUCTION_BUNDLE_SHA256, validate_frozen_bundle_contract\n\n        if bundle.artifact_sha256 == FROZEN_PRODUCTION_BUNDLE_SHA256:\n            validate_frozen_bundle_contract(bundle)\n        if bundle.model_version != MODEL_VERSION:\n            raise ValueError("unexpected independent production model version")\n''',
)
replace_once(
    "src/tennis_genome/calculator/engine.py",
    '''    def calculate(self, matchup: MatchupInput) -> MatchupCalculation:\n        if matchup.foundational.event_date.year <= self.bundle.development_end_year:\n''',
    '''    def calculate(self, matchup: MatchupInput) -> MatchupCalculation:\n        if matchup.prediction_cutoff_at.year <= self.bundle.development_end_year:\n            raise ValueError(\n                "prediction cutoff must occur after the frozen production development period"\n            )\n        if matchup.foundational.event_date.year <= self.bundle.development_end_year:\n''',
)

# 4) Manual prices must bind to canonical IDs, not positional names.
replace_once(
    "src/tennis_genome/calculator/market.py",
    '''    decimal_odds_a: float,\n    decimal_odds_b: float,\n    selection_a_name: str,\n''',
    '''    decimal_odds_a: float,\n    decimal_odds_b: float,\n    selection_a_id: str,\n    selection_b_id: str,\n    selection_a_name: str,\n''',
)
replace_once(
    "src/tennis_genome/calculator/market.py",
    '''    prediction = calculation.prediction\n    payload = {\n''',
    '''    prediction = calculation.prediction\n    if selection_a_id != calculation.player_a_id:\n        raise ValueError("manual market selection A ID does not match canonical Player A")\n    if selection_b_id != calculation.player_b_id:\n        raise ValueError("manual market selection B ID does not match canonical Player B")\n    if selection_a_id == selection_b_id:\n        raise ValueError("manual market selection IDs must be distinct")\n    payload = {\n''',
)
replace_once(
    "src/tennis_genome/calculator/market.py",
    '''        "player_a_id": calculation.player_a_id,\n        "player_b_id": calculation.player_b_id,\n''',
    '''        "player_a_id": selection_a_id,\n        "player_b_id": selection_b_id,\n''',
)
# Replace second occurrence in identity_payload / MarketSnapshot deliberately.
text_path = Path("src/tennis_genome/calculator/market.py")
text = text_path.read_text()
text = text.replace('''        "player_a_id": calculation.player_a_id,\n        "player_b_id": calculation.player_b_id,\n''', '''        "player_a_id": selection_a_id,\n        "player_b_id": selection_b_id,\n''')
text = text.replace('''        player_a_id=calculation.player_a_id,\n        player_b_id=calculation.player_b_id,\n''', '''        player_a_id=selection_a_id,\n        player_b_id=selection_b_id,\n''')
text_path.write_text(text)

# 5) Settlement is provider-derived: terminal status, winner ID and winning reason
# come from the Sportradar payload. Operator-supplied outcome booleans are rejected.
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''class LiveSettlement:\n    match_id: str\n    sportradar_event_id: str\n    actual_start: str | None\n    actual_start_source: str\n    actual_start_exclusion_reason: str | None\n    timeline_sha256: str\n    outcome_a: bool | None\n    retirement: bool\n    walkover: bool\n''',
    '''class LiveSettlement:\n    match_id: str\n    sportradar_event_id: str\n    actual_start: str | None\n    actual_start_source: str\n    actual_start_exclusion_reason: str | None\n    timeline_sha256: str\n    settlement_observed_at: str\n    provider_status: str\n    winner_sportradar_id: str\n    winning_reason: str | None\n''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''        timing = parse_sportradar_actual_start(\n            timeline_payload,\n            expected_event_id=sportradar_event_id,\n        )\n        retirement = _required_bool(raw, "retirement")\n        walkover = _required_bool(raw, "walkover")\n        outcome = _optional_bool(raw, "outcome_a")\n        if not retirement and not walkover and outcome is None:\n            raise ValueError("settled non-excluded rows require outcome_a")\n        result[match_id] = LiveSettlement(\n            match_id=match_id,\n            sportradar_event_id=sportradar_event_id,\n            actual_start=timing.actual_start,\n            actual_start_source=timing.source,\n            actual_start_exclusion_reason=timing.exclusion_reason,\n            timeline_sha256=timing.timeline_sha256,\n            outcome_a=outcome,\n            retirement=retirement,\n            walkover=walkover,\n        )\n''',
    '''        timing = parse_sportradar_actual_start(\n            timeline_payload,\n            expected_event_id=sportradar_event_id,\n        )\n        forbidden_assertions = {"outcome_a", "retirement", "walkover"}.intersection(raw)\n        if forbidden_assertions:\n            raise ValueError(\n                "settlement outcome/finish flags must be provider-derived, not operator supplied"\n            )\n        observed_at = _parse_time(_required_text(raw, "observed_at"))\n        status_payload = _required_object(timeline_payload, "sport_event_status")\n        provider_status = _required_text(status_payload, "status").lower()\n        if provider_status not in {"ended", "closed"}:\n            raise ValueError("settlement requires terminal Sportradar status ended/closed")\n        winner_sportradar_id = _required_text(status_payload, "winner_id")\n        reason_raw = str(status_payload.get("winning_reason", "")).strip().lower()\n        winning_reason = reason_raw or None\n        if winning_reason not in {None, "walkover", "retirement", "defaulted"}:\n            raise ValueError("settlement has unrecognized Sportradar winning_reason")\n        result[match_id] = LiveSettlement(\n            match_id=match_id,\n            sportradar_event_id=sportradar_event_id,\n            actual_start=timing.actual_start,\n            actual_start_source=timing.source,\n            actual_start_exclusion_reason=timing.exclusion_reason,\n            timeline_sha256=timing.timeline_sha256,\n            settlement_observed_at=observed_at.isoformat(),\n            provider_status=provider_status,\n            winner_sportradar_id=winner_sportradar_id,\n            winning_reason=winning_reason,\n        )\n''',
)
replace_once(
    "src/tennis_genome/experiments/pattern_confirm_live.py",
    '''        eligible_outcomes[record.match_id] = SettledOutcome(\n            match_id=record.match_id,\n            outcome_a=settlement.outcome_a,\n            retirement=settlement.retirement,\n            walkover=settlement.walkover,\n        )\n''',
    '''        valid_winners = {record.player_a_sportradar_id, record.player_b_sportradar_id}\n        if settlement.winner_sportradar_id not in valid_winners:\n            raise ValueError("settlement winner ID does not match prospective competitors")\n        retirement = settlement.winning_reason in {"retirement", "defaulted"}\n        walkover = settlement.winning_reason == "walkover"\n        eligible_outcomes[record.match_id] = SettledOutcome(\n            match_id=record.match_id,\n            outcome_a=settlement.winner_sportradar_id == record.player_a_sportradar_id,\n            retirement=retirement,\n            walkover=walkover,\n        )\n''',
)

# Update synthetic timeline fixture to represent the provider settlement authority.
replace_once(
    "tests/test_pattern_confirm_live.py",
    '''def _timeline(\n    *,\n    event_id: str = "sr:sport_event:123",\n    actual_start: str | None = "2026-09-12T17:01:00+00:00",\n) -> dict[str, object]:\n    events: list[dict[str, object]] = []\n    if actual_start is not None:\n        events.append({"id": 1, "type": "match_started", "time": actual_start})\n    return {"sport_event": {"id": event_id}, "timeline": events}\n''',
    '''def _timeline(\n    *,\n    event_id: str = "sr:sport_event:123",\n    actual_start: str | None = "2026-09-12T17:01:00+00:00",\n    status: str = "closed",\n    winner_id: str = "sr:competitor:11",\n    winning_reason: str | None = None,\n) -> dict[str, object]:\n    events: list[dict[str, object]] = []\n    if actual_start is not None:\n        events.append({"id": 1, "type": "match_started", "time": actual_start})\n    status_payload: dict[str, object] = {"status": status, "winner_id": winner_id}\n    if winning_reason is not None:\n        status_payload["winning_reason"] = winning_reason\n    return {\n        "sport_event": {"id": event_id},\n        "sport_event_status": status_payload,\n        "timeline": events,\n    }\n''',
)
# Migrate old settlement fixtures: remove asserted flags and add observed_at.
test_live = Path("tests/test_pattern_confirm_live.py")
text = test_live.read_text()
text = text.replace('''                "outcome_a": True,\n                "retirement": False,\n                "walkover": False,\n''', '''                "observed_at": "2026-09-12T19:00:00+00:00",\n''')
text = text.replace('''                "outcome_a": False,\n                "retirement": False,\n                "walkover": False,\n''', '''                "observed_at": "2026-09-12T19:00:00+00:00",\n''')
# Replace the old boolean-type parametrized test with provider-authority regressions.
old_start = text.index('@pytest.mark.parametrize(\n    ("field", "value"),\n    [\n        ("retirement", "false"),')
old_end = text.index('\n\ndef test_exact_champion_artifact_hashes_are_runtime_pinned', old_start)
replacement = '''def test_settlement_rejects_operator_asserted_outcome_flags() -> None:\n    record = _build()\n    raw: dict[str, object] = {\n        "match_id": record.match_id,\n        "sportradar_event_id": record.sportradar_event_id,\n        "sportradar_timeline": _timeline(),\n        "observed_at": "2026-09-12T19:00:00+00:00",\n        "outcome_a": True,\n    }\n    with pytest.raises(ValueError, match="provider-derived"):\n        load_live_settlements([raw])\n\n\ndef test_settlement_requires_terminal_provider_status() -> None:\n    record = _build()\n    raw = {\n        "match_id": record.match_id,\n        "sportradar_event_id": record.sportradar_event_id,\n        "sportradar_timeline": _timeline(status="live"),\n        "observed_at": "2026-09-12T19:00:00+00:00",\n    }\n    with pytest.raises(ValueError, match="terminal Sportradar status"):\n        load_live_settlements([raw])\n\n\ndef test_settlement_winner_must_match_prospective_competitors() -> None:\n    record = _build()\n    settlements = load_live_settlements(\n        [\n            {\n                "match_id": record.match_id,\n                "sportradar_event_id": record.sportradar_event_id,\n                "sportradar_timeline": _timeline(winner_id="sr:competitor:unrelated"),\n                "observed_at": "2026-09-12T19:00:00+00:00",\n            }\n        ]\n    )\n    with pytest.raises(ValueError, match="winner ID"):\n        evaluate_live_family(\n            [record],\n            settlements,\n            fit=_fit(),\n            profile_artifact=_profile(),\n            core_artifact=_core(),\n            ledger_sha256="6" * 64,\n            settlement_sha256="7" * 64,\n        )\n'''
text = text[:old_start] + replacement + text[old_end:]
test_live.write_text(text)

# Calculator regressions.
test_calc = Path("tests/test_matchup_calculator.py")
text = test_calc.read_text()
text += '''\n\ndef test_matchup_input_rejects_noncanonical_player_order() -> None:\n    _, atp_input, _ = _calculator_and_inputs()\n    with pytest.raises(ValueError, match="canonical ascending"):\n        replace(\n            atp_input,\n            player_a_id=atp_input.player_b_id,\n            player_b_id=atp_input.player_a_id,\n            profile_pair=replace(\n                atp_input.profile_pair,\n                player_a=atp_input.profile_pair.player_b,\n                player_b=atp_input.profile_pair.player_a,\n            ),\n        )\n\n\ndef test_calculator_rejects_pre_freeze_information_cutoff() -> None:\n    calculator, atp_input, _ = _calculator_and_inputs()\n    invalid = replace(\n        atp_input,\n        prediction_cutoff_at=datetime(2020, 1, 1, tzinfo=UTC),\n        created_at=datetime(2026, 9, 19, 18, 0, tzinfo=UTC),\n    )\n    with pytest.raises(ValueError, match="after the frozen production development period"):\n        calculator.calculate(invalid)\n\n\ndef test_matchup_input_rejects_future_dated_profile() -> None:\n    _, atp_input, _ = _calculator_and_inputs()\n    future_profile = replace(\n        atp_input.profile_pair.player_a,\n        valid_from=date(2027, 1, 1),\n    )\n    with pytest.raises(ValueError, match="not yet valid"):\n        replace(\n            atp_input,\n            profile_pair=replace(atp_input.profile_pair, player_a=future_profile),\n        )\n'''
test_calc.write_text(text)

# Contract regression: a sealed fingerprint cannot authenticate altered in-memory content.
test_contract = Path("tests/test_matchup_calculator_contract.py")
text = test_contract.read_text()
text += '''\n\ndef test_frozen_contract_recomputes_in_memory_semantic_digest() -> None:\n    bundle = _valid_frozen_bundle()\n    altered_core = replace(bundle.atp.core, intercept=bundle.atp.core.intercept + 1.0)\n    altered = replace(bundle, atp=replace(bundle.atp, core=altered_core))\n    with pytest.raises(ValueError, match="semantic digest"):\n        validate_frozen_bundle_contract(altered)\n'''
test_contract.write_text(text)

# IO regressions.
test_io = Path("tests/test_matchup_calculator_io.py")
text = test_io.read_text()
text += '''\n\ndef test_provider_neutral_payload_rejects_fractional_best_of() -> None:\n    payload = _payload()\n    payload["best_of"] = 3.9\n    with pytest.raises(ValueError, match="best_of must be integer"):\n        matchup_input_from_dict(payload)\n\n\ndef test_provider_neutral_payload_rejects_nonfinite_numbers() -> None:\n    payload = _payload()\n    payload["foundational"]["elo_logit"] = float("nan")\n    with pytest.raises(ValueError, match="non-finite"):\n        matchup_input_from_dict(payload)\n'''
test_io.write_text(text)

# Manual market IDs and swapped-ID regression.
test_market = Path("tests/test_manual_market_comparison.py")
text = test_market.read_text()
text = text.replace('''        decimal_odds_a=1.85,\n        decimal_odds_b=2.05,\n        selection_a_name="Player A",\n''', '''        decimal_odds_a=1.85,\n        decimal_odds_b=2.05,\n        selection_a_id=calculation.player_a_id,\n        selection_b_id=calculation.player_b_id,\n        selection_a_name="Player A",\n''')
text += '''\n\ndef test_manual_market_rejects_swapped_selection_ids() -> None:\n    calculator, atp_input, _ = _calculator_and_inputs()\n    calculation = calculator.calculate(atp_input)\n    with pytest.raises(ValueError, match="selection A ID"):\n        compare_manual_decimal_odds(\n            comparison_id="comparison-swapped",\n            market_snapshot_id="manual-market-swapped",\n            created_at=datetime(2026, 9, 19, 18, 2, tzinfo=UTC),\n            observed_at=datetime(2026, 9, 19, 18, 1, tzinfo=UTC),\n            calculation=calculation,\n            decimal_odds_a=2.05,\n            decimal_odds_b=1.85,\n            selection_a_id=calculation.player_b_id,\n            selection_b_id=calculation.player_a_id,\n            selection_a_name="Player B",\n            selection_b_name="Player A",\n            bookmaker="MANUAL_TEST",\n            commence_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),\n        )\n'''
test_market.write_text(text)

# Pre-result amendment: implementation-only hardening at N=0.
Path("research/installment_01/pattern_confirm_001_preresult_amendment_011.md").write_text(
    '''# PATTERN-CONFIRM-001 pre-result amendment 011 — provider-derived settlement authority\n\nStatus: **REGISTERED AT PROSPECTIVE N=0 BEFORE ANY ELIGIBLE POST-CUTOFF OUTCOME IS INSPECTED**\n\nThis amendment repairs settlement provenance only. It does not change either frozen\nhypothesis, threshold, correction, sample size, interim look, alpha allocation,\nO'Brien-Fleming boundary, provider choice, five-minute timing rule, model coefficient,\nor promotion rule.\n\n## Settlement authority\n\nA settlement row may no longer supply `outcome_a`, `retirement`, or `walkover` as\noperator assertions. The same Sportradar sport-event payload used for settlement must:\n\n1. reference the prospective record's stable Sportradar event ID;\n2. have terminal `sport_event_status.status` equal to `ended` or `closed`;\n3. contain `winner_id`;\n4. use only the recognized `winning_reason` values `walkover`, `retirement`, or\n   `defaulted` when a nonstandard finish is reported; and\n5. be captured with an explicit timezone-aware `observed_at`.\n\nDuring evaluation the provider `winner_id` is resolved against the prospective\nrecord's already-sealed canonical A/B Sportradar competitor IDs. `outcome_a` is then\nderived mechanically. Retirement/default/walkover exclusion flags are likewise derived\nfrom the provider winning reason. A winner outside the prospective competitors fails\nclosed.\n\nThe objective is to prevent an operator-supplied result or home/away orientation error\nfrom consuming confirmatory N.\n'''
)

print("boundary hardening patch applied")
