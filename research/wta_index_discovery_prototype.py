"""Read-only WTA index candidate discovery; never authorizes intake."""
from datetime import UTC, date, datetime


def discover(index_pages, observed_at):
    """Return candidates and exclusions; quarantine contradictory duplicate identities."""
    observation = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if observation.tzinfo is None:
        raise ValueError("observation must include timezone")
    today = observation.astimezone(UTC).date()
    excluded = {}
    valid = []
    invalid_status_identities = set()
    for page in index_pages:
        for row in page["content"]:
            group = row.get("tournamentGroup")
            try:
                group_id = group["id"] if isinstance(group, dict) else None
                year = row.get("year")
                if (
                    type(group_id) is not int
                    or group_id <= 0
                    or type(year) is not int
                    or year < 2000
                ):
                    raise ValueError("identity")
                end_text = row["endDate"]
                if not isinstance(end_text, str):
                    raise ValueError("date")
                end = date.fromisoformat(end_text)
                start_text = row.get("startDate")
                if start_text is not None:
                    if not isinstance(start_text, str):
                        raise ValueError("start_date")
                    start = date.fromisoformat(start_text)
                    if start > end or start.year != year:
                        raise ValueError("inconsistent_date_range")
                if end.year != year:
                    raise ValueError("year_date_mismatch")
            except (KeyError, TypeError, ValueError):
                key = "invalid_identity_or_date"
                excluded[key] = excluded.get(key, 0) + 1
                continue
            status = row.get("status")
            if status is not None and not isinstance(status, str):
                excluded["invalid_status"] = excluded.get("invalid_status", 0) + 1
                invalid_status_identities.add((group_id, year))
                continue
            valid.append(((group_id, year), end, status))

    grouped = {}
    for identity, end, status in valid:
        grouped.setdefault(identity, []).append((end, status))

    candidates = []
    for identity, records in sorted(grouped.items()):
        if identity in invalid_status_identities:
            excluded["malformed_status_conflict"] = (
                excluded.get("malformed_status_conflict", 0) + len(records)
            )
            continue
        # Conflicting evidence must never be resolved by provider row order.
        if len(set(records)) > 1:
            excluded["conflicting_duplicate"] = (
                excluded.get("conflicting_duplicate", 0) + len(records)
            )
            continue
        if len(records) > 1:
            excluded["duplicate"] = excluded.get("duplicate", 0) + len(records) - 1
        end, status = records[0]
        if status is not None and status not in {"future", "inProgress", "live"}:
            excluded["non_active_status"] = excluded.get("non_active_status", 0) + 1
            continue
        if end < today:
            excluded["ended"] = excluded.get("ended", 0) + 1
            continue
        candidates.append(
            {"group_id": identity[0], "year": identity[1], "end_date": end.isoformat()}
        )
    return {"production_eligible": False, "candidates": candidates, "excluded": excluded}
