from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


path = Path("src/tennis_genome/prospective/pilot.py")
text = path.read_text()
text = replace_once(
    text,
    "from tennis_genome.calculator.io import load_matchup_input\n",
    "from tennis_genome.calculator.io import load_matchup_input\n"
    "from tennis_genome.experiments.pattern_confirm_live import load_live_settlements\n",
    "provider settlement import",
)
text = replace_once(
    text,
    '_FINISH_STATUSES = frozenset({"COMPLETED", "RETIREMENT", "WALKOVER", "DEFAULTED"})\n',
    '_FINISH_STATUSES = frozenset({"COMPLETED", "RETIREMENT", "WALKOVER", "DEFAULTED"})\n'
    '_ANCHOR_SCHEMA = "full-stack-pilot-github-anchor-v1"\n'
    '_ANCHOR_REPOSITORY = "AidanDCM/Tennis-Genome-"\n'
    '_ANCHOR_WORKFLOW_PATH = ".github/workflows/prospective_evidence_anchor.yml"\n'
    '_SETTLEMENT_SCHEMA = "full-stack-pilot-sportradar-settlement-v1"\n',
    "constants",
)
helper_anchor = r'''

def _json_object_bytes(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _required_text(raw: dict[str, object], field: str) -> str:
    value = str(raw.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field} must be non-empty")
    return value


def _verify_anchor_payloads(
    prediction: dict[str, object],
    receipt: dict[str, object],
    run: dict[str, object],
) -> datetime:
    if receipt.get("schema_version") != _ANCHOR_SCHEMA:
        raise ValueError("anchor receipt schema is not supported")
    if receipt.get("provider") != "GITHUB_ACTIONS":
        raise ValueError("anchor receipt provider is not GitHub Actions")
    if receipt.get("repository") != _ANCHOR_REPOSITORY:
        raise ValueError("anchor receipt repository differs from the frozen pilot repository")
    prediction_sha = str(prediction["record_sha256"])
    if receipt.get("prediction_record_sha256") != prediction_sha:
        raise ValueError("anchor receipt prediction SHA does not match prediction record")
    if receipt.get("chain_head_sha256") != prediction_sha:
        raise ValueError("anchor must attest the prediction as the immediate ledger chain head")

    repository = run.get("repository")
    if not isinstance(repository, dict) or repository.get("full_name") != _ANCHOR_REPOSITORY:
        raise ValueError("GitHub run metadata repository does not match the pilot repository")
    if int(run.get("id", -1)) != int(receipt.get("workflow_run_id", -2)):
        raise ValueError("anchor receipt run ID differs from GitHub run metadata")
    if run.get("event") != "workflow_dispatch":
        raise ValueError("anchor run was not triggered by workflow_dispatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("anchor workflow run did not complete successfully")
    if run.get("path") != _ANCHOR_WORKFLOW_PATH:
        raise ValueError("GitHub run metadata is not the prospective anchor workflow")
    if run.get("head_sha") != receipt.get("workflow_source_sha"):
        raise ValueError("anchor workflow source SHA differs from GitHub run metadata")
    run_created_at = _parse_time(_required_text(run, "created_at"), field="anchor.created_at")
    _parse_time(
        _required_text(receipt, "runner_receipt_created_at_utc"),
        field="anchor.runner_receipt_created_at_utc",
    )
    return run_created_at


def _parse_settlement_evidence(
    payload: bytes,
    *,
    prediction: dict[str, object],
) -> tuple[str, str, str | None]:
    raw = _json_object_bytes(payload, label="settlement evidence")
    if raw.get("schema_version") != _SETTLEMENT_SCHEMA:
        raise ValueError("settlement evidence schema is not supported")
    forbidden = {
        "winner_player_id",
        "winner_id",
        "finish_status",
        "actual_start",
        "outcome_a",
        "retirement",
        "walkover",
    }.intersection(raw)
    if forbidden:
        raise ValueError(
            "settlement winner/status/start must be derived from provider evidence, not asserted"
        )
    if raw.get("match_id") != prediction.get("match_id"):
        raise ValueError("settlement evidence match_id differs from prediction")
    if raw.get("player_a_canonical_id") != prediction.get("player_a_id"):
        raise ValueError("settlement evidence canonical Player A differs from prediction")
    if raw.get("player_b_canonical_id") != prediction.get("player_b_id"):
        raise ValueError("settlement evidence canonical Player B differs from prediction")
    player_a_sr = _required_text(raw, "player_a_sportradar_id")
    player_b_sr = _required_text(raw, "player_b_sportradar_id")
    if player_a_sr == player_b_sr:
        raise ValueError("settlement Sportradar competitor IDs must be distinct")

    settlements = load_live_settlements([raw])
    provider = settlements[str(prediction["match_id"])]
    if provider.winner_sportradar_id == player_a_sr:
        winner = str(prediction["player_a_id"])
    elif provider.winner_sportradar_id == player_b_sr:
        winner = str(prediction["player_b_id"])
    else:
        raise ValueError("provider-derived winner does not match retained competitor mapping")
    if provider.winning_reason == "walkover":
        status = "WALKOVER"
    elif provider.winning_reason == "retirement":
        status = "RETIREMENT"
    elif provider.winning_reason == "defaulted":
        status = "DEFAULTED"
    else:
        status = "COMPLETED"
    return winner, status, provider.actual_start
'''
text = replace_once(
    text,
    "\ndef _record_sha256(record_without_sha: dict[str, object]) -> str:\n",
    helper_anchor + "\n\ndef _record_sha256(record_without_sha: dict[str, object]) -> str:\n",
    "helpers",
)
text = replace_once(
    text,
    "        settled_predictions: set[str] = set()\n        prediction_count = 0\n        settlement_count = 0\n",
    "        settled_predictions: set[str] = set()\n"
    "        anchors_by_prediction: dict[str, dict[str, object]] = {}\n"
    "        prediction_count = 0\n        anchor_count = 0\n        settlement_count = 0\n",
    "verify state",
)
anchor_branch = r'''            elif record_type == "ANCHOR_ATTESTATION":
                anchor_count += 1
                prediction_sha = str(record.get("prediction_record_sha256", ""))
                prediction = prediction_by_sha.get(prediction_sha)
                if prediction is None:
                    raise ValueError("anchor does not reference an earlier prediction record")
                if prediction_sha in anchors_by_prediction:
                    raise ValueError(f"prediction anchored more than once: {prediction_sha}")
                receipt_sha = str(record.get("anchor_receipt_sha256", ""))
                run_sha = str(record.get("github_run_metadata_sha256", ""))
                if receipt_sha not in evidence_hashes or run_sha not in evidence_hashes:
                    raise ValueError("anchor evidence hashes are not retained")
                receipt = _json_object_bytes(
                    (self.evidence_dir / receipt_sha).read_bytes(),
                    label="anchor receipt",
                )
                run = _json_object_bytes(
                    (self.evidence_dir / run_sha).read_bytes(),
                    label="GitHub run metadata",
                )
                created_at = _verify_anchor_payloads(prediction, receipt, run)
                if record.get("anchor_created_at") != created_at.isoformat():
                    raise ValueError("anchor created_at does not reproduce from GitHub metadata")
                if int(record.get("workflow_run_id", -1)) != int(run["id"]):
                    raise ValueError("anchor workflow run ID does not reproduce")
                anchors_by_prediction[prediction_sha] = record
'''
text = replace_once(
    text,
    '            elif record_type == "SETTLEMENT":\n',
    anchor_branch + '            elif record_type == "SETTLEMENT":\n',
    "anchor verify branch",
)
old_primary = '''                expected_primary = status == "COMPLETED" and expected_timing == "PRE_START_VERIFIED"
                if bool(record.get("primary_evaluation_eligible")) != expected_primary:
                    raise ValueError("primary evaluation eligibility does not reproduce")
'''
new_primary = '''                anchor = anchors_by_prediction.get(prediction_sha)
                if anchor is None:
                    expected_anchor_status = "ANCHOR_MISSING"
                elif actual_start is None:
                    expected_anchor_status = "ACTUAL_START_UNVERIFIED"
                else:
                    anchor_created = _parse_time(
                        str(anchor["anchor_created_at"]), field="anchor_created_at"
                    )
                    expected_anchor_status = (
                        "PRE_START_ANCHORED"
                        if anchor_created < actual_start
                        else "ANCHOR_NOT_PRE_START"
                    )
                if record.get("anchor_status") != expected_anchor_status:
                    raise ValueError("settlement anchor status does not reproduce")
                expected_primary = (
                    status == "COMPLETED"
                    and expected_timing == "PRE_START_VERIFIED"
                    and expected_anchor_status == "PRE_START_ANCHORED"
                )
                if bool(record.get("primary_evaluation_eligible")) != expected_primary:
                    raise ValueError("primary evaluation eligibility does not reproduce")
'''
text = replace_once(text, old_primary, new_primary, "settlement eligibility")
text = replace_once(
    text,
    '            "prediction_count": prediction_count,\n            "settlement_count": settlement_count,\n',
    '            "prediction_count": prediction_count,\n            "anchor_count": anchor_count,\n            "settlement_count": settlement_count,\n',
    "verify report",
)
text = text.replace(
    "removed.append(str(path.relative_to(self.root)))",
    "removed.append(path.relative_to(self.root).as_posix())",
)
text = text.replace(
    "removed.append(str(self.lock_path.relative_to(self.root)))",
    "removed.append(self.lock_path.relative_to(self.root).as_posix())",
)

start = text.index("\ndef settle_prediction(\n")
end = text.index("\n\ndef _build_parser()", start)
replacement = r'''

def attest_anchor(
    *,
    store: ProspectivePilotStore,
    prediction_record_sha256: str,
    anchor_receipt_path: Path,
    github_run_metadata_path: Path,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        prediction = store.find_record(prediction_record_sha256)
        if prediction.get("record_type") != "PREDICTION_COMMIT":
            raise ValueError("anchor must reference a prediction commit record")
        if any(
            record.get("record_type") == "ANCHOR_ATTESTATION"
            and record.get("prediction_record_sha256") == prediction_record_sha256
            for record in store.records()
        ):
            raise ValueError("prediction already has an anchor attestation")

        receipt_payload = anchor_receipt_path.read_bytes()
        run_payload = github_run_metadata_path.read_bytes()
        receipt = _json_object_bytes(receipt_payload, label="anchor receipt")
        run = _json_object_bytes(run_payload, label="GitHub run metadata")
        created_at = _verify_anchor_payloads(prediction, receipt, run)
        receipt_sha = store._store_evidence_bytes(receipt_payload)
        run_sha = store._store_evidence_bytes(run_payload)
        return store._append_record(
            {
                "record_type": "ANCHOR_ATTESTATION",
                "prediction_record_sha256": prediction_record_sha256,
                "prediction_id": prediction["prediction_id"],
                "match_id": prediction["match_id"],
                "tour": prediction["tour"],
                "workflow_run_id": int(run["id"]),
                "workflow_run_url": receipt["workflow_run_url"],
                "anchor_created_at": created_at.isoformat(),
                "anchor_receipt_sha256": receipt_sha,
                "github_run_metadata_sha256": run_sha,
                "evidence_sha256": [receipt_sha, run_sha],
            }
        )


def settle_prediction(
    *,
    store: ProspectivePilotStore,
    prediction_record_sha256: str,
    settlement_evidence_path: Path,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    with store.write_lock():
        store.verify()
        prediction = store.find_record(prediction_record_sha256)
        if prediction.get("record_type") != "PREDICTION_COMMIT":
            raise ValueError("settlement must reference a prediction commit record")
        if any(
            record.get("record_type") == "SETTLEMENT"
            and record.get("prediction_record_sha256") == prediction_record_sha256
            for record in store.records()
        ):
            raise ValueError("prediction already has a settlement record")

        settlement_payload = settlement_evidence_path.read_bytes()
        winner_player_id, status, actual_start = _parse_settlement_evidence(
            settlement_payload, prediction=prediction
        )
        settled_at = now()
        if settled_at.tzinfo is None or settled_at.utcoffset() is None:
            raise ValueError("settlement clock must return a timezone-aware datetime")
        settled_at = settled_at.astimezone(UTC)
        parsed_actual = (
            None if actual_start is None else _parse_time(actual_start, field="actual_start")
        )
        if parsed_actual is not None and settled_at < parsed_actual:
            raise ValueError("settlement cannot be recorded before actual start")

        committed = _parse_time(str(prediction["committed_at"]), field="committed_at")
        timing_status = (
            "ACTUAL_START_UNVERIFIED"
            if parsed_actual is None
            else ("PRE_START_VERIFIED" if committed < parsed_actual else "COMMIT_NOT_PRE_START")
        )
        anchor = next(
            (
                record
                for record in store.records()
                if record.get("record_type") == "ANCHOR_ATTESTATION"
                and record.get("prediction_record_sha256") == prediction_record_sha256
            ),
            None,
        )
        if anchor is None:
            anchor_status = "ANCHOR_MISSING"
        elif parsed_actual is None:
            anchor_status = "ACTUAL_START_UNVERIFIED"
        else:
            anchor_created = _parse_time(str(anchor["anchor_created_at"]), field="anchor_created_at")
            anchor_status = (
                "PRE_START_ANCHORED"
                if anchor_created < parsed_actual
                else "ANCHOR_NOT_PRE_START"
            )
        primary_eligible = (
            status == "COMPLETED"
            and timing_status == "PRE_START_VERIFIED"
            and anchor_status == "PRE_START_ANCHORED"
        )
        settlement_sha = store._store_evidence_bytes(settlement_payload)
        return store._append_record(
            {
                "record_type": "SETTLEMENT",
                "prediction_record_sha256": prediction_record_sha256,
                "prediction_id": prediction["prediction_id"],
                "match_id": prediction["match_id"],
                "tour": prediction["tour"],
                "winner_player_id": winner_player_id,
                "finish_status": status,
                "actual_start": None if parsed_actual is None else parsed_actual.isoformat(),
                "settled_at": settled_at.isoformat(),
                "timing_status": timing_status,
                "anchor_status": anchor_status,
                "primary_evaluation_eligible": primary_eligible,
                "settlement_evidence_sha256": settlement_sha,
                "evidence_sha256": [settlement_sha],
            }
        )
'''
text = text[:start] + replacement + text[end:]

text = replace_once(
    text,
    '    settle = subparsers.add_parser("settle", help="append a separate settlement record")\n'
    '    settle.add_argument("--store", required=True, type=Path)\n'
    '    settle.add_argument("--prediction-record-sha256", required=True)\n'
    '    settle.add_argument("--winner-player-id", required=True)\n'
    '    settle.add_argument("--finish-status", required=True, choices=sorted(_FINISH_STATUSES))\n'
    '    settle.add_argument("--actual-start")\n'
    '    settle.add_argument("--settlement-evidence", required=True, type=Path)\n',
    '    anchor = subparsers.add_parser("attest-anchor", help="append a verified GitHub anchor attestation")\n'
    '    anchor.add_argument("--store", required=True, type=Path)\n'
    '    anchor.add_argument("--prediction-record-sha256", required=True)\n'
    '    anchor.add_argument("--anchor-receipt", required=True, type=Path)\n'
    '    anchor.add_argument("--github-run-metadata", required=True, type=Path)\n\n'
    '    settle = subparsers.add_parser("settle", help="derive and append provider settlement")\n'
    '    settle.add_argument("--store", required=True, type=Path)\n'
    '    settle.add_argument("--prediction-record-sha256", required=True)\n'
    '    settle.add_argument("--settlement-evidence", required=True, type=Path)\n',
    "parser commands",
)
old_main = '''    elif args.command == "settle":
        result = settle_prediction(
            store=store,
            prediction_record_sha256=args.prediction_record_sha256,
            winner_player_id=args.winner_player_id,
            finish_status=args.finish_status,
            settlement_evidence_path=args.settlement_evidence,
            actual_start=args.actual_start,
        )
    elif args.command == "verify":
'''
new_main = '''    elif args.command == "attest-anchor":
        result = attest_anchor(
            store=store,
            prediction_record_sha256=args.prediction_record_sha256,
            anchor_receipt_path=args.anchor_receipt,
            github_run_metadata_path=args.github_run_metadata,
        )
    elif args.command == "settle":
        result = settle_prediction(
            store=store,
            prediction_record_sha256=args.prediction_record_sha256,
            settlement_evidence_path=args.settlement_evidence,
        )
    elif args.command == "verify":
'''
text = replace_once(text, old_main, new_main, "main dispatch")
path.write_text(text)

# Tests: helpers and deliberate-failure probes.
tests = Path("tests/test_prospective_pilot.py")
t = tests.read_text()
helper = r'''

def _anchor_files(
    tmp_path: Path,
    prediction: dict[str, object],
    *,
    created_at: str = "2026-09-13T16:05:00+00:00",
) -> tuple[Path, Path]:
    run_id = 123456789
    receipt = {
        "schema_version": "full-stack-pilot-github-anchor-v1",
        "provider": "GITHUB_ACTIONS",
        "repository": "AidanDCM/Tennis-Genome-",
        "workflow_source_sha": "d" * 40,
        "workflow_run_id": run_id,
        "workflow_run_attempt": 1,
        "workflow_run_url": f"https://github.com/AidanDCM/Tennis-Genome-/actions/runs/{run_id}",
        "prediction_record_sha256": prediction["record_sha256"],
        "chain_head_sha256": prediction["record_sha256"],
        "runner_receipt_created_at_utc": created_at,
    }
    run = {
        "id": run_id,
        "event": "workflow_dispatch",
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/prospective_evidence_anchor.yml",
        "head_sha": "d" * 40,
        "created_at": created_at,
        "repository": {"full_name": "AidanDCM/Tennis-Genome-"},
    }
    receipt_path = tmp_path / "anchor.json"
    run_path = tmp_path / "run.json"
    receipt_path.write_text(json.dumps(receipt) + "\n")
    run_path.write_text(json.dumps(run) + "\n")
    return receipt_path, run_path


def _attest_anchor(
    tmp_path: Path,
    store: pilot.ProspectivePilotStore,
    prediction: dict[str, object],
    *,
    created_at: str = "2026-09-13T16:05:00+00:00",
) -> dict[str, object]:
    receipt_path, run_path = _anchor_files(tmp_path, prediction, created_at=created_at)
    return pilot.attest_anchor(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        anchor_receipt_path=receipt_path,
        github_run_metadata_path=run_path,
    )


def _settlement_file(
    tmp_path: Path,
    prediction: dict[str, object],
    *,
    winner: str = "a",
    reason: str | None = None,
    actual_start: str = "2026-09-13T17:01:00+00:00",
    asserted: dict[str, object] | None = None,
) -> Path:
    winner_id = "sr:competitor:a" if winner == "a" else "sr:competitor:b"
    status: dict[str, object] = {"status": "ended", "winner_id": winner_id}
    if reason is not None:
        status["winning_reason"] = reason
    raw: dict[str, object] = {
        "schema_version": "full-stack-pilot-sportradar-settlement-v1",
        "match_id": prediction["match_id"],
        "sportradar_event_id": "sr:sport_event:pilot-1",
        "player_a_canonical_id": prediction["player_a_id"],
        "player_b_canonical_id": prediction["player_b_id"],
        "player_a_sportradar_id": "sr:competitor:a",
        "player_b_sportradar_id": "sr:competitor:b",
        "observed_at": "2026-09-13T18:00:00+00:00",
        "sportradar_timeline": {
            "sport_event": {"id": "sr:sport_event:pilot-1"},
            "sport_event_status": status,
            "timeline": [{"id": 1, "type": "match_started", "time": actual_start}],
        },
    }
    if asserted:
        raw.update(asserted)
    target = tmp_path / f"settlement-{winner}-{reason or 'completed'}.json"
    target.write_text(json.dumps(raw) + "\n")
    return target
'''
t = replace_once(
    t,
    "\ndef test_prediction_commit_is_hash_chained_and_retains_exact_evidence(\n",
    helper + "\n\ndef test_prediction_commit_is_hash_chained_and_retains_exact_evidence(\n",
    "test helpers",
)
old_test = '''    settlement_source = tmp_path / "settlement.json"
    settlement_source.write_text('{"winner_id":"canonical-a","status":"completed"}\n')

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        winner_player_id="canonical-a",
        finish_status="COMPLETED",
        settlement_evidence_path=settlement_source,
        actual_start="2026-09-13T17:01:00+00:00",
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["timing_status"] == "PRE_START_VERIFIED"
    assert settlement["primary_evaluation_eligible"] is True
    report = store.verify()
    assert report["record_count"] == 2
    assert report["settlement_count"] == 1
'''
new_test = '''    _attest_anchor(tmp_path, store, prediction)
    settlement_source = _settlement_file(tmp_path, prediction, winner="a")

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=settlement_source,
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["winner_player_id"] == "canonical-a"
    assert settlement["finish_status"] == "COMPLETED"
    assert settlement["timing_status"] == "PRE_START_VERIFIED"
    assert settlement["anchor_status"] == "PRE_START_ANCHORED"
    assert settlement["primary_evaluation_eligible"] is True
    report = store.verify()
    assert report["record_count"] == 3
    assert report["anchor_count"] == 1
    assert report["settlement_count"] == 1
'''
t = replace_once(t, old_test, new_test, "primary settlement test")
old_late = '''    settlement_source = tmp_path / "settlement.json"
    settlement_source.write_text('{"winner_id":"canonical-b","status":"completed"}\n')

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        winner_player_id="canonical-b",
        finish_status="COMPLETED",
        settlement_evidence_path=settlement_source,
        actual_start="2026-09-13T15:59:30+00:00",
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["timing_status"] == "COMMIT_NOT_PRE_START"
    assert settlement["primary_evaluation_eligible"] is False
    assert store.verify()["status"] == "VERIFIED"
'''
new_late = '''    settlement_source = _settlement_file(
        tmp_path,
        prediction,
        winner="b",
        actual_start="2026-09-13T15:59:30+00:00",
    )

    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=settlement_source,
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )

    assert settlement["timing_status"] == "COMMIT_NOT_PRE_START"
    assert settlement["anchor_status"] == "ANCHOR_MISSING"
    assert settlement["primary_evaluation_eligible"] is False
    assert store.verify()["status"] == "VERIFIED"
'''
t = replace_once(t, old_late, new_late, "late settlement test")
t += r'''


def test_missing_anchor_excludes_otherwise_valid_completed_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(tmp_path, prediction),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["timing_status"] == "PRE_START_VERIFIED"
    assert settlement["anchor_status"] == "ANCHOR_MISSING"
    assert settlement["primary_evaluation_eligible"] is False


def test_late_anchor_is_retained_but_excluded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(
        tmp_path,
        store,
        prediction,
        created_at="2026-09-13T17:02:00+00:00",
    )
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(tmp_path, prediction),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["anchor_status"] == "ANCHOR_NOT_PRE_START"
    assert settlement["primary_evaluation_eligible"] is False


def test_anchor_receipt_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    receipt_path, run_path = _anchor_files(tmp_path, prediction)
    receipt = json.loads(receipt_path.read_text())
    receipt["prediction_record_sha256"] = "f" * 64
    receipt_path.write_text(json.dumps(receipt) + "\n")
    with pytest.raises(ValueError, match="prediction SHA"):
        pilot.attest_anchor(
            store=store,
            prediction_record_sha256=str(prediction["record_sha256"]),
            anchor_receipt_path=receipt_path,
            github_run_metadata_path=run_path,
        )


def test_settlement_rejects_operator_asserted_outcome_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(tmp_path, store, prediction)
    evidence = _settlement_file(
        tmp_path,
        prediction,
        asserted={"winner_player_id": "canonical-b", "finish_status": "COMPLETED"},
    )
    with pytest.raises(ValueError, match="provider evidence"):
        pilot.settle_prediction(
            store=store,
            prediction_record_sha256=str(prediction["record_sha256"]),
            settlement_evidence_path=evidence,
            now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
        )


def test_provider_retirement_is_derived_from_retained_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, prediction = _commit_fixture(tmp_path, monkeypatch)
    _attest_anchor(tmp_path, store, prediction)
    settlement = pilot.settle_prediction(
        store=store,
        prediction_record_sha256=str(prediction["record_sha256"]),
        settlement_evidence_path=_settlement_file(
            tmp_path, prediction, winner="b", reason="retirement"
        ),
        now=lambda: datetime(2026, 9, 13, 18, 0, tzinfo=UTC),
    )
    assert settlement["winner_player_id"] == "canonical-b"
    assert settlement["finish_status"] == "RETIREMENT"
    assert settlement["primary_evaluation_eligible"] is False


def test_recovery_paths_are_posix_portable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _ = _commit_fixture(tmp_path, monkeypatch)
    (store.records_dir / "orphan.tmp").write_text("partial")
    report = store.recover()
    assert all("\\" not in item for item in report["recovery_removed"])
'''
tests.write_text(t)

# Documentation alignment.
docs = Path("docs/prospective_full_stack_pilot.md")
d = docs.read_text()
d = d.replace(
    "The anchor receipt is not itself sufficient for primary eligibility. During supervised audit, retain the exact receipt and retrieve the corresponding GitHub Actions run metadata directly from GitHub. Verify the run is the successful `Prospective Evidence Anchor` workflow, its server-side `created_at` precedes verified actual start, its repository/source SHA agree with the receipt, and its receipt prediction/chain hashes agree with the local prediction record. The GitHub run ID/URL is the durable external reference.\n",
    "The anchor receipt is not itself sufficient for primary eligibility. During supervised audit, retain the exact receipt and retrieve the corresponding GitHub Actions run metadata directly from GitHub. Then append an `ANCHOR_ATTESTATION` record with `attest-anchor`; the ledger verifier checks the receipt/run metadata pair and settlement eligibility requires that server-side run `created_at` precede verified actual start. The GitHub run ID/URL remains the durable external reference that can be rechecked independently.\n\nExample:\n\n```text\npython -m tennis_genome.prospective.pilot attest-anchor \\\n  --store prospective/full_stack_forward_001 \\\n  --prediction-record-sha256 <prediction-record-sha> \\\n  --anchor-receipt prospective_anchor_receipt.json \\\n  --github-run-metadata github_run.json\n```\n",
)
d = d.replace(
    "python -m tennis_genome.prospective.pilot settle \\\n  --store prospective/full_stack_forward_001 \\\n  --prediction-record-sha256 <prediction-record-sha> \\\n  --winner-player-id <canonical-player-id> \\\n  --finish-status COMPLETED \\\n  --actual-start 2026-09-20T14:03:21-04:00 \\\n  --settlement-evidence settlement_source.json\n",
    "python -m tennis_genome.prospective.pilot settle \\\n  --store prospective/full_stack_forward_001 \\\n  --prediction-record-sha256 <prediction-record-sha> \\\n  --settlement-evidence sportradar_settlement_capture.json\n",
)
d = d.replace(
    "Allowed finish statuses are `COMPLETED`, `RETIREMENT`, `WALKOVER`, and `DEFAULTED`. The canonical winner must be one of the two players sealed into the prediction record. Exact settlement source bytes are retained.\n",
    "The v1 pilot settlement capture is Sportradar-derived. Winner, finish status, and actual start are read from the retained `sportradar_timeline`; operator-supplied winner/status/start assertions are rejected. The capture also binds the Sportradar competitor IDs to the canonical A/B IDs already sealed in the prediction. Exact settlement source bytes are retained.\n",
)
d = d.replace(
    "A record is mechanically marked `primary_evaluation_eligible=true` only when the match is `COMPLETED` and the prediction commitment precedes verified actual start. This flag is about the registered forward-evaluation cohort, not a wagering decision.\n",
    "A record is mechanically marked `primary_evaluation_eligible=true` only when the match is provider-derived `COMPLETED`, the prediction commitment precedes verified actual start, and a prior verified GitHub anchor attestation has server-side `created_at` before actual start. Missing/late anchors remain explicit exclusions. This flag is about the registered forward-evaluation cohort, not a wagering decision.\n",
)
docs.write_text(d)

protocol = Path("research/installment_01/full_stack_forward_001_protocol.md")
p = protocol.read_text()
p = p.replace(
    "- the commitment time is strictly before independently retained actual-start evidence;\n- the externally retained GitHub anchor run is authenticated during supervised audit and its server-side `created_at` is strictly before verified actual start;\n- the match finished normally with `finish_status=COMPLETED`;\n- the settlement winner is one of the two canonical competitors and the settlement record/evidence passes verification.\n",
    "- the commitment time is strictly before independently retained actual-start evidence;\n- an `ANCHOR_ATTESTATION` record verifies the exact GitHub receipt/run-metadata pair and its server-side `created_at` is strictly before verified actual start;\n- the match finished normally with provider-derived `finish_status=COMPLETED`;\n- winner, finish status, and actual start are derived from retained Sportradar timeline evidence and the provider competitor mapping resolves to the two canonical competitors;\n- the settlement record/evidence passes verification.\n",
)
protocol.write_text(p)
