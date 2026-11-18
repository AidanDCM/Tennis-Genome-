"""Read-only WTA index candidate discovery; never authorizes intake."""
from datetime import UTC, date, datetime


def discover(index_pages, observed_at):
    """Return candidates and exclusions; fail closed on malformed date/identity."""
    observation = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    if observation.tzinfo is None:
        raise ValueError("observation must include timezone")
    today = observation.astimezone(UTC).date()
    candidates, excluded, seen = [], {}, set()
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
                if end.year != year:
                    raise ValueError("year_date_mismatch")
            except (KeyError, TypeError, ValueError):
                key = "invalid_identity_or_date"
                excluded[key] = excluded.get(key, 0) + 1
                continue
            identity = (group_id, year)
            if identity in seen:
                excluded["duplicate"] = excluded.get("duplicate", 0) + 1
                continue
            seen.add(identity)
            # Provider status is an independent veto; absence retains legacy behavior.
            status = row.get("status")
            if status is not None and status not in {"future", "inProgress", "live"}:
                excluded["non_active_status"] = excluded.get("non_active_status", 0) + 1
                continue
            if end < today:
                excluded["ended"] = excluded.get("ended", 0) + 1
                continue
            candidates.append({"group_id": group_id, "year": year, "end_date": end.isoformat()})
    return {"production_eligible": False, "candidates": candidates, "excluded": excluded}
