from __future__ import annotations

import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal

from .bootstrap import (
    AUDIO_EXTS,
    VISUAL_EXTS,
    ensure_system_assets,
    hide_folder_windows,
    replace_managed_asset,
)
from .defaults import (
    DEFAULT_PRESET,
    DEFAULT_SETTINGS,
    LEGACY_COMPANION_KEYS,
    SYSTEM_AUDIO_ID,
    SYSTEM_VISUAL_ID,
)
from .persistence import read_json, write_json
from .session_repository import SessionRepository
from .utils import detect_kind, new_id, now_iso, relative_or_absolute, resolve_stored_path


class Store(QObject):
    resources_changed = Signal()
    presets_changed = Signal()
    sessions_changed = Signal()
    settings_changed = Signal()
    branding_changed = Signal()
    defaults_changed = Signal()
    visual_framing_changed = Signal(str)

    def __init__(self, app_root: Path):
        super().__init__()
        self.app_root = Path(app_root).resolve()
        self.resources_dir = self.app_root / "resources"
        self.data_dir = self.app_root / ".cyndaquil"
        self.library_dir = self.resources_dir / "library"
        self.backup_dir = self.resources_dir / "backups"
        self.branding_dir = self.data_dir / "branding"
        self.defaults_dir = self.data_dir / "defaults"

        self.resources_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        hide_folder_windows(self.data_dir)

        self.system_assets = ensure_system_assets(self.data_dir)

        self.state_path = self.data_dir / "state.json"
        self.resources_path = self.data_dir / "resources.json"
        self.sessions_path = self.data_dir / "sessions.json"

        state = self._read(self.state_path, {})
        self.settings: dict[str, Any] = deepcopy(DEFAULT_SETTINGS)
        saved_settings = state.get("settings", {})
        self.settings.update(saved_settings)
        self._migrate_companion_settings(saved_settings)
        self.presets: list[dict[str, Any]] = state.get("presets", [])
        self.resources: list[dict[str, Any]] = self._read(self.resources_path, [])
        self._history = SessionRepository(
            self.sessions_path,
            writer=lambda records: self._write(self.sessions_path, records),
            changed=self.sessions_changed.emit,
        )
        self._migrate_history_records()

        self._ensure_default_preset()
        self.save_state()
        self.sync_system_resources()
        self.sync_internal_resources()

        self._resource_timer = QTimer(self)
        self._resource_timer.setInterval(1800)
        self._resource_timer.timeout.connect(self._poll_resource_folder)
        self._resource_timer.start()

    def _migrate_companion_settings(self, saved_settings: dict[str, Any]) -> None:
        """Migrate the old single-window companion once, then remove its keys."""
        legacy_present = any(key in saved_settings for key in LEGACY_COMPANION_KEYS)
        if legacy_present:
            # Preserve the user's broad intent without carrying old geometry logic forward.
            if "companion_show_visual" in saved_settings:
                self.settings["visual_companion_enabled"] = bool(
                    saved_settings.get("companion_show_visual")
                )
            if "companion_width" in saved_settings:
                try:
                    old_width = int(saved_settings.get("companion_width", 360))
                    self.settings["visual_companion_width"] = max(160, min(1600, old_width))
                except (TypeError, ValueError):
                    pass
            if "companion_height" in saved_settings:
                try:
                    old_height = int(saved_settings.get("companion_height", 280))
                    self.settings["visual_companion_height"] = max(100, min(1200, old_height))
                except (TypeError, ValueError):
                    pass
            if "companion_opacity" in saved_settings:
                try:
                    opacity = max(35, min(100, int(saved_settings.get("companion_opacity", 96))))
                    self.settings["visual_companion_opacity"] = opacity
                    self.settings["control_companion_opacity"] = opacity
                except (TypeError, ValueError):
                    pass
            if "companion_clock_size" in saved_settings:
                try:
                    self.settings["control_companion_clock_size"] = max(
                        12, min(120, int(saved_settings.get("companion_clock_size", 32)))
                    )
                except (TypeError, ValueError):
                    pass
            if "companion_button_size" in saved_settings:
                try:
                    self.settings["control_companion_button_size"] = max(
                        7, min(32, int(saved_settings.get("companion_button_size", 10)))
                    )
                except (TypeError, ValueError):
                    pass
            for old_key, new_key in (
                ("companion_show_clock", "control_companion_show_timer"),
                ("companion_show_status", "control_companion_show_status"),
                ("companion_show_pause", "control_companion_show_pause"),
                ("companion_show_adjust", "control_companion_show_adjust"),
                ("companion_show_main", "control_companion_show_main"),
                ("companion_show_finish", "control_companion_show_finish"),
                ("companion_show_config", "control_companion_show_customize"),
            ):
                if old_key in saved_settings:
                    self.settings[new_key] = bool(saved_settings.get(old_key))

        for key in LEGACY_COMPANION_KEYS:
            self.settings.pop(key, None)

    def _migrate_history_records(self) -> None:
        """Remove obsolete Break data while preserving raw timestamps and focused time."""
        changed = False
        if "break_minutes" in self.settings:
            self.settings.pop("break_minutes", None)
            changed = True
        for session in self.sessions:
            if "break_seconds" in session:
                session.pop("break_seconds", None)
                changed = True
        if changed:
            self.save_sessions()

    # ---------- persistence ----------

    _read = staticmethod(read_json)
    _write = staticmethod(write_json)

    def save_state(self) -> None:
        self._write(self.state_path, {"settings": self.settings, "presets": self.presets})

    def save_resources(self) -> None:
        self._write(self.resources_path, self.resources)

    def save_sessions(self) -> None:
        self._write(self.sessions_path, self.sessions)

    # ---------- settings / defaults ----------

    def update_settings(self, updates: dict[str, Any]) -> None:
        self.settings.update(updates)
        self.save_state()
        self.settings_changed.emit()

    def _resolve_setting_path(self, key: str) -> Path | None:
        value = self.settings.get(key)
        path = resolve_stored_path(value, self.app_root) if value else None
        return path if path and path.exists() else None

    def current_icon_path(self) -> Path:
        return self._resolve_setting_path("custom_icon_path") or self.system_assets["icon"]

    def current_default_audio_path(self) -> Path:
        return self._resolve_setting_path("default_audio_path") or self.system_assets["audio"]

    def current_default_visual_path(self) -> Path:
        return self._resolve_setting_path("default_visual_path") or self.system_assets["visual"]

    def set_custom_icon(self, source: Path) -> None:
        destination = replace_managed_asset(
            Path(source),
            self.branding_dir,
            "custom_icon",
            {".png", ".jpg", ".jpeg", ".bmp", ".webp"},
        )
        self.settings["custom_icon_path"] = relative_or_absolute(destination, self.app_root)
        self.save_state()
        self.branding_changed.emit()

    def reset_custom_icon(self) -> None:
        for candidate in self.branding_dir.glob("custom_icon.*"):
            try:
                candidate.unlink()
            except OSError:
                pass
        self.settings["custom_icon_path"] = None
        self.save_state()
        self.branding_changed.emit()

    def set_default_audio(self, source: Path) -> None:
        destination = replace_managed_asset(
            Path(source),
            self.defaults_dir,
            "custom_audio",
            AUDIO_EXTS,
        )
        self.settings["default_audio_path"] = relative_or_absolute(destination, self.app_root)
        self.save_state()
        self.sync_system_resources()
        self.defaults_changed.emit()

    def reset_default_audio(self) -> None:
        for candidate in self.defaults_dir.glob("custom_audio.*"):
            try:
                candidate.unlink()
            except OSError:
                pass
        self.settings["default_audio_path"] = None
        self.save_state()
        self.sync_system_resources()
        self.defaults_changed.emit()

    def set_default_visual(self, source: Path) -> None:
        destination = replace_managed_asset(
            Path(source),
            self.defaults_dir,
            "custom_visual",
            VISUAL_EXTS,
        )
        self.settings["default_visual_path"] = relative_or_absolute(destination, self.app_root)
        self.save_state()
        self.sync_system_resources()
        self.defaults_changed.emit()

    def reset_default_visual(self) -> None:
        for candidate in self.defaults_dir.glob("custom_visual.*"):
            try:
                candidate.unlink()
            except OSError:
                pass
        self.settings["default_visual_path"] = None
        self.save_state()
        self.sync_system_resources()
        self.defaults_changed.emit()

    # ---------- visual framing ----------

    def visual_framing(self, resource_id: str | None) -> dict[str, Any]:
        defaults = {"fit": "contain", "zoom": 100, "pan_x": 0, "pan_y": 0}
        if not resource_id:
            return defaults
        profiles = self.settings.get("visual_framing_profiles") or {}
        profile = profiles.get(str(resource_id)) or {}
        fit = profile.get("fit", "contain")
        if fit not in {"contain", "cover", "stretch"}:
            fit = "contain"
        return {
            "fit": fit,
            "zoom": max(100, min(400, int(profile.get("zoom", 100) or 100))),
            "pan_x": max(-100, min(100, int(profile.get("pan_x", 0) or 0))),
            "pan_y": max(-100, min(100, int(profile.get("pan_y", 0) or 0))),
        }

    def update_visual_framing(self, resource_id: str | None, framing: dict[str, Any]) -> None:
        if not resource_id:
            return
        current = self.visual_framing(resource_id)
        current.update(dict(framing))
        fit = current.get("fit", "contain")
        if fit not in {"contain", "cover", "stretch"}:
            fit = "contain"
        normalized = {
            "fit": fit,
            "zoom": max(100, min(400, int(current.get("zoom", 100) or 100))),
            "pan_x": max(-100, min(100, int(current.get("pan_x", 0) or 0))),
            "pan_y": max(-100, min(100, int(current.get("pan_y", 0) or 0))),
        }
        profiles = dict(self.settings.get("visual_framing_profiles") or {})
        profiles[str(resource_id)] = normalized
        self.settings["visual_framing_profiles"] = profiles
        self.save_state()
        self.visual_framing_changed.emit(str(resource_id))

    def reset_visual_framing(self, resource_id: str | None) -> None:
        if not resource_id:
            return
        profiles = dict(self.settings.get("visual_framing_profiles") or {})
        profiles.pop(str(resource_id), None)
        self.settings["visual_framing_profiles"] = profiles
        self.save_state()
        self.visual_framing_changed.emit(str(resource_id))

    # ---------- presets ----------

    def _ensure_default_preset(self) -> None:
        default = next((p for p in self.presets if p.get("id") == "default"), None)
        if default is None:
            self.presets.insert(0, deepcopy(DEFAULT_PRESET))
            return

        default["name"] = "Default"
        default.setdefault("mode", "stopwatch")
        default.setdefault("minutes", 50)

        # A permanent fallback is always available. Users can replace it in
        # Settings or select different resources in the Default preset.
        if not default.get("music_ids"):
            default["music_ids"] = [SYSTEM_AUDIO_ID]
        if not default.get("visual_id"):
            default["visual_id"] = SYSTEM_VISUAL_ID

    def preset_by_id(self, preset_id: str | None):
        return next((p for p in self.presets if p.get("id") == preset_id), None)

    def upsert_preset(self, preset: dict[str, Any]) -> None:
        preset = dict(preset)
        if preset.get("id") == "default":
            preset["name"] = "Default"
            if not preset.get("music_ids"):
                preset["music_ids"] = [SYSTEM_AUDIO_ID]
            if not preset.get("visual_id"):
                preset["visual_id"] = SYSTEM_VISUAL_ID

        for index, existing in enumerate(self.presets):
            if existing.get("id") == preset.get("id"):
                self.presets[index] = preset
                break
        else:
            preset.setdefault("id", new_id())
            self.presets.append(preset)

        self._ensure_default_preset()
        self.save_state()
        self.presets_changed.emit()

    def delete_preset(self, preset_id: str) -> bool:
        if preset_id == "default":
            return False
        self.presets = [p for p in self.presets if p.get("id") != preset_id]
        self._ensure_default_preset()
        self.save_state()
        self.presets_changed.emit()
        return True

    # ---------- resources ----------

    def resource_by_id(self, resource_id: str | None):
        if not resource_id:
            return None
        return next((r for r in self.resources if r.get("id") == resource_id), None)

    def _path(self, stored: str | None) -> Path | None:
        return resolve_stored_path(stored, self.app_root)

    def _inside_resources(self, path: Path | None) -> bool:
        if path is None:
            return False
        try:
            path.resolve().relative_to(self.resources_dir.resolve())
            return True
        except Exception:
            return False

    def resolve_resource(self, resource_id: str | None) -> tuple[Path | None, str | None]:
        item = self.resource_by_id(resource_id)
        if not item:
            return None, None

        primary = self._path(item.get("primary_path"))
        if primary and primary.exists():
            return primary, "primary"

        backup = self._path(item.get("backup_path"))
        if backup and backup.exists():
            return backup, "backup"

        return None, None

    def resource_status(self, resource_id: str) -> str:
        item = self.resource_by_id(resource_id)
        if not item:
            return "Missing"

        primary = self._path(item.get("primary_path"))
        backup = self._path(item.get("backup_path"))

        if primary and primary.exists():
            return "Available"
        if backup and backup.exists():
            return "Using Backup"
        return "Missing"

    def sync_system_resources(self) -> None:
        audio_path = self.current_default_audio_path()
        visual_path = self.current_default_visual_path()

        changed = False
        specs = [
            (
                SYSTEM_AUDIO_ID,
                "Default Ember Ambience",
                "audio",
                audio_path,
            ),
            (
                SYSTEM_VISUAL_ID,
                "Default Ember Visual",
                detect_kind(visual_path),
                visual_path,
            ),
        ]

        for rid, name, kind, path in specs:
            item = self.resource_by_id(rid)
            payload = {
                "id": rid,
                "name": name,
                "filename": path.name,
                "kind": kind,
                "primary_path": relative_or_absolute(path, self.app_root),
                "backup_path": None,
                "managed": True,
                "auto_internal": False,
                "special": True,
                "system_default": True,
                "added_at": item.get("added_at", now_iso()) if item else now_iso(),
                "size": path.stat().st_size if path.exists() else None,
            }
            if item is None:
                self.resources.insert(0, payload)
                changed = True
            else:
                for key, value in payload.items():
                    if item.get(key) != value:
                        item[key] = value
                        changed = True

        self._ensure_default_preset()
        if changed:
            self.save_resources()
            self.save_state()
            self.resources_changed.emit()
            self.presets_changed.emit()

    def add_resource(self, source: Path, import_primary=False, keep_backup=False) -> dict[str, Any]:
        source = Path(source).resolve()
        kind = detect_kind(source)
        if kind == "other":
            raise ValueError("Unsupported resource type.")

        rid = new_id()
        backup = None

        if import_primary:
            self.library_dir.mkdir(parents=True, exist_ok=True)
            destination = self.library_dir / f"{rid[:8]}_{source.name}"
            shutil.copy2(source, destination)
            primary = relative_or_absolute(destination, self.app_root)
            managed = True
        else:
            primary = str(source)
            managed = False
            if keep_backup:
                self.backup_dir.mkdir(parents=True, exist_ok=True)
                destination = self.backup_dir / f"{rid[:8]}_{source.name}"
                shutil.copy2(source, destination)
                backup = relative_or_absolute(destination, self.app_root)

        item = {
            "id": rid,
            "name": source.stem,
            "filename": source.name,
            "kind": kind,
            "primary_path": primary,
            "backup_path": backup,
            "managed": managed,
            "auto_internal": False,
            "special": False,
            "added_at": now_iso(),
            "size": source.stat().st_size if source.exists() else None,
        }
        self.resources.append(item)
        self.save_resources()
        self.resources_changed.emit()
        return item

    def relink_resource(self, resource_id: str, path: Path) -> None:
        item = self.resource_by_id(resource_id)
        if not item or item.get("special"):
            return

        path = Path(path).resolve()
        item["primary_path"] = relative_or_absolute(path, self.app_root)
        item["filename"] = path.name
        item["name"] = path.stem
        item["kind"] = detect_kind(path)
        item["managed"] = self._inside_resources(path)
        item["auto_internal"] = item["managed"]
        try:
            item["size"] = path.stat().st_size
        except OSError:
            pass

        self.save_resources()
        self.resources_changed.emit()

    def make_backup(self, resource_id: str) -> bool:
        item = self.resource_by_id(resource_id)
        if not item or item.get("special"):
            return False

        source, _ = self.resolve_resource(resource_id)
        if not source:
            return False

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        destination = self.backup_dir / f"{resource_id[:8]}_{item.get('filename', source.name)}"
        shutil.copy2(source, destination)
        item["backup_path"] = relative_or_absolute(destination, self.app_root)

        self.save_resources()
        self.resources_changed.emit()
        return True

    def _clear_resource_from_presets(self, resource_id: str) -> bool:
        changed = False
        for preset in self.presets:
            if preset.get("id") == "default" and resource_id in {SYSTEM_AUDIO_ID, SYSTEM_VISUAL_ID}:
                continue

            music = preset.get("music_ids", [])
            new_music = [rid for rid in music if rid != resource_id]
            if new_music != music:
                preset["music_ids"] = new_music
                changed = True

            if preset.get("visual_id") == resource_id:
                preset["visual_id"] = None
                changed = True

        self._ensure_default_preset()
        return changed

    def remove_resource(self, resource_id: str, delete_local_files=False) -> None:
        item = self.resource_by_id(resource_id)
        if not item or item.get("special"):
            return

        if delete_local_files:
            for key in ("primary_path", "backup_path"):
                path = self._path(item.get(key))
                if path and path.exists() and self._inside_resources(path):
                    try:
                        path.unlink()
                    except OSError:
                        pass

        self.resources = [r for r in self.resources if r.get("id") != resource_id]
        presets_changed = self._clear_resource_from_presets(resource_id)
        profiles = dict(self.settings.get("visual_framing_profiles") or {})
        framing_changed = profiles.pop(str(resource_id), None) is not None
        if framing_changed:
            self.settings["visual_framing_profiles"] = profiles

        self.save_resources()
        if presets_changed or framing_changed:
            self.save_state()

        self.resources_changed.emit()
        if presets_changed:
            self.presets_changed.emit()

    def _is_scan_candidate(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            relative = path.resolve().relative_to(self.resources_dir.resolve())
        except ValueError:
            return False

        if relative.parts and relative.parts[0].lower() == "backups":
            return False
        return detect_kind(path) != "other"

    def sync_internal_resources(self) -> dict[str, int]:
        """
        Keep the library synchronized with files physically inside resources/.

        - New supported files are added automatically.
        - Moved internal files are matched by filename when possible.
        - Deleted internal files are removed from the library.
        - External links are never deleted automatically.
        """
        candidates = [
            p.resolve() for p in self.resources_dir.rglob("*") if self._is_scan_candidate(p)
        ]
        candidate_set = set(candidates)
        claimed: set[Path] = set()

        added = 0
        removed = 0
        moved = 0
        resources_changed = False
        presets_changed = False

        # Existing internal entries.
        internal_items = [
            r
            for r in self.resources
            if not r.get("special") and (r.get("auto_internal") or r.get("managed"))
        ]

        # First claim paths that still exist.
        for item in internal_items:
            primary = self._path(item.get("primary_path"))
            if primary and primary.exists() and primary in candidate_set:
                claimed.add(primary)

        # Attempt to relocate missing internal entries by filename.
        for item in list(internal_items):
            primary = self._path(item.get("primary_path"))
            if primary and primary.exists():
                continue

            filename = str(item.get("filename", "")).lower()
            matches = [p for p in candidates if p not in claimed and p.name.lower() == filename]
            if len(matches) == 1:
                found = matches[0]
                item["primary_path"] = relative_or_absolute(found, self.app_root)
                item["name"] = found.stem
                item["kind"] = detect_kind(found)
                item["managed"] = True
                item["auto_internal"] = True
                claimed.add(found)
                moved += 1
                resources_changed = True
                continue

            # Internal file really disappeared: remove its entry.
            rid = item.get("id")
            self.resources = [r for r in self.resources if r.get("id") != rid]
            presets_changed = self._clear_resource_from_presets(rid) or presets_changed
            removed += 1
            resources_changed = True

        # Add unclaimed new files.
        known_paths = set()
        for item in self.resources:
            if item.get("special"):
                continue
            path = self._path(item.get("primary_path"))
            if path and path.exists() and self._inside_resources(path):
                known_paths.add(path.resolve())

        for path in candidates:
            if path in known_paths:
                continue
            rid = new_id()
            item = {
                "id": rid,
                "name": path.stem,
                "filename": path.name,
                "kind": detect_kind(path),
                "primary_path": relative_or_absolute(path, self.app_root),
                "backup_path": None,
                "managed": True,
                "auto_internal": True,
                "special": False,
                "added_at": now_iso(),
                "size": path.stat().st_size,
            }
            self.resources.append(item)
            known_paths.add(path)
            added += 1
            resources_changed = True

        if resources_changed:
            self.save_resources()
            self.resources_changed.emit()
        if presets_changed:
            self.save_state()
            self.presets_changed.emit()

        return {"added": added, "removed": removed, "moved": moved}

    def _poll_resource_folder(self) -> None:
        self.sync_system_resources()
        self.sync_internal_resources()

    def repair_resources(self) -> dict[str, int]:
        sync = self.sync_internal_resources()
        repaired = sync["moved"]
        backup_ready = 0

        by_name: dict[str, list[Path]] = {}
        for path in self.resources_dir.rglob("*"):
            if self._is_scan_candidate(path):
                by_name.setdefault(path.name.lower(), []).append(path.resolve())

        changed = False
        for item in self.resources:
            if item.get("special"):
                continue

            primary = self._path(item.get("primary_path"))
            if primary and primary.exists():
                continue

            backup = self._path(item.get("backup_path"))
            if backup and backup.exists():
                backup_ready += 1

            matches = by_name.get(str(item.get("filename", "")).lower(), [])
            if len(matches) == 1:
                item["primary_path"] = relative_or_absolute(matches[0], self.app_root)
                item["managed"] = True
                item["auto_internal"] = True
                repaired += 1
                changed = True

        if changed:
            self.save_resources()
            self.resources_changed.emit()

        return {
            "added": sync["added"],
            "removed": sync["removed"],
            "repaired": repaired,
            "backup_ready": backup_ready,
        }

    # ---------- history ----------

    @property
    def sessions(self) -> list[dict[str, Any]]:
        return self._history.records

    def add_session(self, session: dict[str, Any]) -> None:
        self._history.add_session(session)

    def session_by_id(self, session_id: str | None):
        return self._history.session_by_id(session_id)

    def update_session(self, session_id: str | None, updated: dict[str, Any]) -> bool:
        return self._history.update_session(session_id, updated)

    def update_session_seconds(self, session_id: str, seconds: int) -> None:
        self._history.update_session_seconds(session_id, seconds)

    def update_session_tags(self, session_ids, tags, *, remove=False) -> int:
        return self._history.update_session_tags(session_ids, tags, remove=remove)

    def delete_session(self, session_id: str) -> None:
        self._history.delete_session(session_id)
