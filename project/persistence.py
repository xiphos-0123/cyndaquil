"""Durable JSON storage without changing Cyndaquil's on-disk formats.

Missing files initialize normally. Unreadable or malformed existing files fail
closed, so startup cannot replace saved records with empty defaults. Each save
retains the previous valid document beside it as ``<filename>.bak``.
"""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path


class PersistenceError(RuntimeError):
    """A load or save failed; the caller must not claim the operation succeeded."""


def _validate(data, fallback) -> None:
    if not isinstance(data, type(fallback)):
        raise ValueError(f"Expected {type(fallback).__name__} document")
    if isinstance(data, list) and any(not isinstance(item, dict) for item in data):
        raise ValueError("Expected a list of records")
    if isinstance(data, dict):
        if not isinstance(data.get('settings', {}), dict):
            raise ValueError("Expected settings object")
        presets = data.get('presets', [])
        if not isinstance(presets, list) or any(not isinstance(p, dict) for p in presets):
            raise ValueError("Expected a list of presets")


def read_json(path: Path, fallback):
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
        _validate(data, fallback)
        return data
    except FileNotFoundError:
        return deepcopy(fallback)
    except (OSError, ValueError, TypeError) as error:
        raise PersistenceError(
            f"Cannot read {path}. Your existing file has not been replaced. "
            f"Check this file and its .bak backup before trying again.\n{error}"
        ) from error


def _atomic_replace(path: Path, contents: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.',
                                         suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_json(path: Path, data) -> None:
    try:
        _validate(data, data)
        contents = json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False).encode('utf-8')
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            previous = path.read_bytes()
        except FileNotFoundError:
            previous = None
        if previous is not None:
            _validate(json.loads(previous), data)
            _atomic_replace(path.with_name(path.name + '.bak'), previous)
        _atomic_replace(path, contents)
    except (OSError, ValueError, TypeError) as error:
        raise PersistenceError(f"Cannot save {path}. Check disk space and permissions.\n{error}") from error
