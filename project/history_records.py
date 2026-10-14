"""Session duration/date formatting and validation shared by History views."""

from __future__ import annotations

from datetime import datetime

from .utils import parse_iso_datetime


def _seconds_to_editor(value: int | float | None) -> str:
    seconds = max(0, int(value or 0))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _parse_duration(text: str, field_name: str) -> int:
    raw = text.strip().lower()
    if not raw:
        return 0
    try:
        if raw.endswith("h"):
            return max(0, int(round(float(raw[:-1].strip()) * 3600)))
        if raw.endswith("m"):
            return max(0, int(round(float(raw[:-1].strip()) * 60)))
        if raw.endswith("s"):
            return max(0, int(round(float(raw[:-1].strip()))))
        if ":" not in raw:
            return max(0, int(round(float(raw))))
        parts = raw.split(":")
        if len(parts) == 2:
            minutes, seconds = [int(part.strip()) for part in parts]
            if seconds < 0 or seconds >= 60:
                raise ValueError
            return max(0, minutes * 60 + seconds)
        if len(parts) == 3:
            hours, minutes, seconds = [int(part.strip()) for part in parts]
            if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
                raise ValueError
            return max(0, hours * 3600 + minutes * 60 + seconds)
    except (TypeError, ValueError):
        pass
    raise ValueError(
        f"{field_name} must be HH:MM:SS, MM:SS, seconds, or a value such as 45m / 1.5h."
    )


def _datetime_to_editor(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    if parsed:
        return parsed.isoformat(sep=" ", timespec="seconds")
    return str(value or "")


def _parse_datetime(text: str, field_name: str) -> str:
    raw = text.strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be a valid date/time, for example 2026-10-09 18:45:00+05:30."
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.isoformat(timespec="seconds")


def _session_span_seconds(session: dict) -> int | None:
    start = parse_iso_datetime(session.get("started_at"))
    end = parse_iso_datetime(session.get("ended_at"))
    if not start or not end:
        return None
    return max(0, int(round((end - start).total_seconds())))


def _session_nonfocus_seconds(session: dict) -> int | None:
    span = _session_span_seconds(session)
    if span is None:
        return None
    return max(0, span - max(0, int(session.get("focused_seconds", 0) or 0)))


def _short_datetime(value: str | None) -> str:
    parsed = parse_iso_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M") if parsed else "—"
