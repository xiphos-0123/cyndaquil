# Developing Cyndaquil

Cyndaquil is a PySide6 desktop app. `Cyndaquil.pyw` calls `project.app.run`.
`project.main.run` remains available for existing launchers.

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `app.py` | Qt initialization, single-instance guard, loading data, startup |
| `main.py` | Main window, session actions, tray and quit behavior |
| `navigation.py` | Sidebar destinations, selection, version label |
| `history.py` | Read-only history browsing, date/tag filters, selected notes |
| `statistics_view.py` | Statistics widgets and reporting controls |
| `history_analytics.py` | Reporting-day totals, windows, trends |
| `history_chart.py` | Chart painting |
| `session_entry.py` | Explicitly saved session edits, collapsed distractions |
| `session_repository.py` | History updates committed before notifying the UI |
| `persistence.py` | Validated JSON reads, atomic saves, previous-file backups |
| `defaults.py` | Built-in defaults and legacy setting names |
| `store.py` | Shared resource/settings/preset facade and Qt signals |
| `session.py` | Focus timing, temporary notes, tags, idle detection |
| Other page/media modules | Their named page, playback, or companion feature |

## Checks

Install application requirements with `python -m pip install -r requirements.txt`.
For formatting and linting, install `ruff==0.17.0` separately; it is a development
tool and is not required to launch Cyndaquil.

```sh
python -m unittest discover -s tests -v
ruff check project tests
ruff format --check project tests
```

Headless Linux checks need `QT_QPA_PLATFORM=offscreen` and
`QT_AUDIO_BACKEND=pulseaudio`. Use writable XDG cache/config directories when the
home directory is read-only. Desktop, audio-output and Windows integration still
need interactive verification.

Tests use temporary data directories. Never run a destructive test against the
real `.cyndaquil` folder. Preserve unknown record fields, IDs, original timestamps,
notes and distraction formatting. Existing sessions without tags remain valid.
Filtering must not mutate records. Keep user media, local backups and branding.

Python bytecode is generated, ignored, and reproducible. Do not commit it. The
existing tracked `.cyndaquil` files are intentionally retained in this cleanup;
ignore rules do not remove previously tracked records or replace anyone's data.
