"""History operations isolated from Qt, resource scans, and page widgets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .history_filters import normalize_tags
from .persistence import read_json
from .utils import now_iso, parse_iso_datetime


class SessionRepository:
    def __init__(self, path: Path, writer: Callable, changed: Callable):
        self.records: list[dict[str, Any]] = read_json(path, [])
        self._writer = writer
        self._changed = changed

    def _commit(self, records) -> None:
        # The durable write must succeed before memory or UI signals change.
        self._writer(records)
        self.records = records
        self._changed()

    def add_session(self, session: dict[str, Any]) -> None:
        session = dict(session)
        session.pop("break_seconds", None)
        if "tags" in session:
            session["tags"] = normalize_tags(session["tags"])
        updated = [*self.records, session]
        self._commit(updated)

    def session_by_id(self, session_id: str | None):
        if not session_id:
            return None
        return next((item for item in self.records if item.get("id") == session_id), None)

    def update_session(self, session_id: str | None, updated: dict[str, Any]) -> bool:
        """Replace the editable contents of one History entry while preserving its ID."""
        if not session_id:
            return False

        for index, existing in enumerate(self.records):
            if existing.get("id") != session_id:
                continue

            merged = dict(existing)
            merged.update(dict(updated))
            merged["id"] = session_id
            merged["edited_at"] = now_iso()
            if "tags" in merged:
                merged["tags"] = normalize_tags(merged["tags"])

            # Keep the stored record internally consistent even if it was
            # imported from an older Cyndaquil version.
            merged.pop("break_seconds", None)
            for key in ("target_seconds", "focused_seconds"):
                try:
                    merged[key] = max(0, int(merged.get(key, 0) or 0))
                except (TypeError, ValueError):
                    merged[key] = 0

            merged["mission"] = str(merged.get("mission", "") or "")
            merged["preset_name"] = str(merged.get("preset_name", "") or "")
            merged["completion_note"] = str(merged.get("completion_note", "") or "")
            merged["mode"] = "timer" if merged.get("mode") == "timer" else "stopwatch"
            merged["distractions"] = [
                str(value).strip()
                for value in (merged.get("distractions") or [])
                if str(value).strip()
            ]
            merged["music_ids"] = [str(value) for value in (merged.get("music_ids") or []) if value]

            sessions = list(self.records)
            sessions[index] = merged
            self._commit(sessions)
            return True

        return False

    def update_sessions(self, updates: dict, *, expected: dict | None = None) -> int:
        """Apply explicit patches atomically without normalizing untouched fields."""
        allowed = {
            "mission",
            "preset_name",
            "completion_note",
            "tags",
            "mode",
            "started_at",
            "ended_at",
            "focused_seconds",
            "target_seconds",
        }
        if not updates:
            return 0
        selected = [record for record in self.records if record.get("id") in updates]
        if len(selected) != len(updates) or len({r.get("id") for r in selected}) != len(updates):
            raise ValueError(
                "A selected session is missing or has a duplicate ID. Reopen the editor."
            )
        sessions = list(self.records)
        changed = 0
        for index, record in enumerate(sessions):
            sid = record.get("id")
            if sid not in updates:
                continue
            if expected is not None and expected.get(sid) != record:
                raise ValueError(
                    "A selected session changed while editing. Reopen the editor to load it."
                )
            patch = dict(updates[sid])
            if set(patch) - allowed:
                raise ValueError("This edit contains unsupported fields.")
            for key in ("mission", "preset_name", "completion_note", "started_at", "ended_at"):
                if key in patch and not isinstance(patch[key], str):
                    raise ValueError(f"{key} must be text.")
            for key in ("focused_seconds", "target_seconds"):
                if key in patch and (type(patch[key]) is not int or patch[key] < 0):
                    raise ValueError(f"{key} must be a nonnegative duration.")
            if "mode" in patch and patch["mode"] not in {"timer", "stopwatch"}:
                raise ValueError("Choose Timer or Stopwatch.")
            if "tags" in patch:
                patch["tags"] = normalize_tags(patch["tags"])
            merged = {**record, **patch}
            for key in ("started_at", "ended_at"):
                if key in patch and patch[key] and parse_iso_datetime(patch[key]) is None:
                    raise ValueError("Enter a valid session timestamp.")
            start = parse_iso_datetime(merged.get("started_at"))
            end = parse_iso_datetime(merged.get("ended_at"))
            if {"started_at", "ended_at"} & patch.keys() and start and end and end < start:
                raise ValueError(
                    "Finished At cannot be earlier than Started At for any selected session."
                )
            if merged != record:
                sessions[index] = {**merged, "edited_at": now_iso()}
                changed += 1
        if changed:
            self._commit(sessions)
        return changed

    def update_session_seconds(self, session_id: str, seconds: int) -> None:
        # Retained for compatibility with older callers. The History page now
        # uses update_session() through the full Session Entry editor.
        item = self.session_by_id(session_id)
        if not item:
            return
        updated = dict(item)
        updated["focused_seconds"] = max(0, int(seconds))
        self.update_session(session_id, updated)

    def update_session_tags(self, session_ids, tags, *, remove=False) -> int:
        """Update selected records together; commit to memory only after saving."""
        selected = set(session_ids)
        tags = normalize_tags(tags)
        if not selected or not tags:
            return 0
        removed = {tag.casefold() for tag in tags}
        sessions = list(self.records)
        changed = 0
        for index, session in enumerate(sessions):
            if session.get("id") not in selected:
                continue
            existing = normalize_tags(session.get("tags", []))
            updated = (
                [tag for tag in existing if tag.casefold() not in removed]
                if remove
                else normalize_tags([*existing, *tags])
            )
            if updated == existing:
                continue
            sessions[index] = {**session, "tags": updated, "edited_at": now_iso()}
            changed += 1
        if changed:
            self._commit(sessions)
        return changed

    def delete_session(self, session_id: str) -> None:
        sessions = [s for s in self.records if s.get("id") != session_id]
        self._commit(sessions)
