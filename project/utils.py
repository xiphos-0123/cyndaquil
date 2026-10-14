from __future__ import annotations

import os
import sys
import uuid
from datetime import date, datetime, time, timedelta
from pathlib import Path

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
GIF_EXTS = {".gif"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def format_seconds(value: float | int) -> str:
    seconds = max(0, int(round(value)))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def reporting_day_key(moment: datetime, start_hour: int = 0) -> date:
    """Return the logical reporting date for an aware/local datetime."""
    hour = max(0, min(23, int(start_hour)))
    local = moment if moment.tzinfo is not None else moment.astimezone()
    shifted = local - timedelta(hours=hour)
    return shifted.date()


def reporting_day_bounds(day: date, start_hour: int = 0, tz=None) -> tuple[datetime, datetime]:
    hour = max(0, min(23, int(start_hour)))
    tz = tz or datetime.now().astimezone().tzinfo
    start = datetime.combine(day, time(hour=hour), tzinfo=tz)
    return start, start + timedelta(days=1)


def current_reporting_day(start_hour: int = 0, now: datetime | None = None) -> date:
    return reporting_day_key(now or datetime.now().astimezone(), start_hour)


def detect_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in GIF_EXTS:
        return "gif"
    if ext in VIDEO_EXTS:
        return "video"
    return "other"


def reveal_path(path: Path) -> None:
    path = Path(path)
    target = path if path.is_dir() else path.parent
    if sys.platform.startswith("win"):
        os.startfile(str(target))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{target}"')
    else:
        os.system(f'xdg-open "{target}" >/dev/null 2>&1 &')


def relative_or_absolute(path: Path, root: Path) -> str:
    path = Path(path).resolve()
    try:
        return str(path.relative_to(root.resolve()))
    except ValueError:
        return str(path)


def resolve_stored_path(value: str | None, root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def filename_from_stored(value: str | None) -> str:
    return Path(value).name if value else ""
