"""Pure reporting-day calculations, independent of Qt and file storage."""

from datetime import date, timedelta

from .utils import parse_iso_datetime, reporting_day_key


def daily_totals(sessions, start_hour: int) -> dict[date, int]:
    totals: dict[date, int] = {}
    for session in sessions:
        started = parse_iso_datetime(session.get("started_at"))
        if not started:
            continue
        key = reporting_day_key(started, start_hour)
        totals[key] = totals.get(key, 0) + max(0, int(session.get("focused_seconds", 0) or 0))
    return totals


def window_days(end_day: date, days: int) -> list[date]:
    return [end_day - timedelta(days=i) for i in range(days - 1, -1, -1)]


def window_total(totals: dict[date, int], end_day: date, days: int) -> int:
    return sum(totals.get(day, 0) for day in window_days(end_day, days))


def trend(totals: dict[date, int], end_day: date, days: int) -> tuple[int, int, float | None]:
    current = window_total(totals, end_day, days)
    previous_end = end_day - timedelta(days=days)
    previous = window_total(totals, previous_end, days)
    if previous > 0:
        return current, previous, ((current - previous) / previous) * 100
    return current, previous, None


def best_window(
    totals: dict[date, int], current_day: date, days: int
) -> tuple[date | None, date | None, int]:
    if not totals:
        return None, None, 0
    first = min(totals)
    if first > current_day:
        return None, None, 0
    best_total = -1
    best_start = first
    best_end = first
    end = first
    while end <= current_day:
        total = window_total(totals, end, days)
        if total > best_total:
            best_total = total
            best_end = end
            best_start = end - timedelta(days=days - 1)
        end += timedelta(days=1)
    return best_start, best_end, max(0, best_total)
