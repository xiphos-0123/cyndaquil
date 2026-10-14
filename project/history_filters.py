"""Read-only history selection and backward-compatible session tags."""

from __future__ import annotations

from datetime import date

from .utils import parse_iso_datetime, reporting_day_key


def normalize_tags(values) -> list[str]:
    """Trim tags and deduplicate case-insensitively, retaining display spelling."""
    if isinstance(values, str):
        values = values.split(",")
    if not isinstance(values, (list, tuple)):
        return []
    result = []
    seen = set()
    for value in values:
        if not isinstance(value, str):
            continue
        tag = value.strip()
        if tag and tag.casefold() not in seen:
            result.append(tag)
            seen.add(tag.casefold())
    return result


def filter_sessions(
    sessions,
    *,
    start: date | None = None,
    end: date | None = None,
    start_hour: int = 0,
    tags=(),
    tag_mode: str = "include",
) -> list[dict]:
    """Select reporting dates inclusively; match any selected tag.

    Undated legacy records remain visible in All time. No record is modified.
    """
    wanted = {tag.casefold() for tag in normalize_tags(tags)}
    result = []
    for session in sessions:
        if wanted:
            assigned = {tag.casefold() for tag in normalize_tags(session.get("tags", []))}
            matches = bool(assigned & wanted)
            if (tag_mode == "include" and not matches) or (tag_mode == "exclude" and matches):
                continue
        if start is not None or end is not None:
            moment = parse_iso_datetime(session.get("started_at"))
            if moment is None:
                continue
            day = reporting_day_key(moment, start_hour)
            if (start is not None and day < start) or (end is not None and day > end):
                continue
        result.append(session)
    return result
