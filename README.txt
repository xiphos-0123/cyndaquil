CYNDAQUIL
=========

Cyndaquil is a desktop focus environment built around timed work sessions,
ambience, a configurable floating companion, and lightweight session history.

INSTALLATION
------------
1. Extract the complete Cyndaquil folder.
2. Run:

       Install Cyndaquil.bat

   This installer does one thing only: install the packages listed in
   requirements.txt.

3. Launch:

       Cyndaquil.pyw

Cyndaquil does not create shortcuts, change folder icons, create desktop.ini,
modify File Explorer icons, or change the Windows .pyw file association.

APPLICATION ICON
----------------
The application icon is managed from:

    Application Settings > Appearance

Choose "Choose Application Icon..." to use your own image.

The selected image is used only while Cyndaquil is running:
- inside the application
- on the taskbar
- in the system tray

If no custom image is configured, Cyndaquil generates and uses its built-in
fallback emblem.

DEFAULT PRESET
--------------
The permanent Default preset always has usable fallback ambience.

Cyndaquil generates:
- a default ember visual
- a quiet synthetic ember ambience audio file

These generated files live inside Cyndaquil's hidden .cyndaquil data folder,
not inside your Resource Library.

You can replace either fallback from:

    Application Settings > Default Preset Ambience

If a custom default file is later missing, Cyndaquil automatically returns to
the generated fallback.

RESOURCE LIBRARY
----------------
The resources folder is your internal media library.

Any supported media file placed anywhere inside:

    resources\

is detected automatically while Cyndaquil is running.

If an internally managed resource is deleted from the resources folder,
Cyndaquil removes the corresponding library entry and cleans preset references.

External resources behave differently:
- they remain in the library if the original file is missing
- they can be relinked later
- they can optionally keep a backup in resources\backups\

You can also trigger an immediate scan from:
- Resource Library > Scan Resource Library
- Application Settings > Scan Resource Library

FOCUS PRESETS
-------------
The Focus Presets page manages reusable combinations of:
- Stopwatch or Timer mode
- Timer duration
- Audio playlist
- Visual ambience

The Default preset is permanent. It can be edited but not deleted.

Saving a preset displays a visible "Preset Saved" confirmation.

SESSION COMPLETION
------------------
When finishing a session you may:

Save to History
    Saves focused time, start/finish timestamps, session information, and the optional
    completion note.

Finish as Failure — Do Not Save
    Ends the active session without creating a History entry.

FLOATING COMPANIONS
-------------------
Cyndaquil now uses two independent companion windows instead of one combined
layout.

VISUAL COMPANION
The Visual Companion contains only the active preset visual.

It can be configured with:
- Enabled / Disabled
- Width
- Height
- Lock to Visual Aspect Ratio
- Opacity

When aspect lock is enabled, the visual keeps its native ratio. Images and GIFs
use their actual source dimensions; video uses a stable widescreen fallback
until platform video metadata is available.

Double-click the Visual Companion to return directly to the main Cyndaquil
window. You do not need a Main button in the Control Companion if you keep the
visual enabled.

CONTROL COMPANION
The Control Companion contains the timer and selected controls in one compact
window. It does not share dimensions with the visual.

It can be configured with:
- Enabled / Disabled
- Width
- Opacity
- Timer Text Size
- Button Text Size
- Button Height
- Panel Padding
- Button Spacing
- Timer visibility
- Session Status visibility
- Pause / Resume
- -1 / +1 Minute
- Main Window
- Finish Session
- Customize

The control window determines its own height from its visible content. This
removes the old Timer Panel Height, Control Bar Height, and Visual Area
percentage calculations that previously competed with each other.

Application Settings shows separate live previews for both windows using the
selected Focus Preset. The same settings are also available from the live
companion Customize command.

Disable either companion independently. If both are disabled, opening Floating
Companions leaves the main window open.

SINGLE INSTANCE
---------------
Cyndaquil permits only one running application instance at a time.

Launching Cyndaquil again while it is already running does not create another
background copy. The existing instance is asked to restore its main window.

MAIN WINDOW
-----------
Cyndaquil opens maximized by default. This is the application's native
workspace layout and is designed to use the available screen space.

The Focus Session page includes:
- Session Setup
- Selected Preset preview
- Today's Progress
- Session Shortcuts

During an active session, the page becomes the main session controller.

KEYBOARD SHORTCUTS
------------------
Space
    Pause / Resume

Ctrl + D
    Distraction Dump

DATA
----
Cyndaquil stores application state in:

    .cyndaquil\

This includes:
- settings
- focus presets
- session history
- generated fallback assets
- custom runtime application icon
- custom Default preset ambience

The folder is hidden on Windows when possible.

SUPPORTED RESOURCE TYPES
------------------------
Audio:
mp3, wav, ogg, flac, m4a, aac

Images:
png, jpg, jpeg, bmp, webp

Animated:
gif

Video:
mp4, mkv, mov, avi, webm, m4v

Video codec support depends on the multimedia codecs available to Qt on the
operating system.


REPORTING DAYS AND PRODUCTIVITY
--------------------------------
History uses a configurable Reporting Day Start instead of assuming every workday
runs from midnight to midnight. Change it directly on the History page whenever
your schedule changes. Raw session timestamps are never rewritten.

History includes:
- Current Reporting Day focused time
- Last 7 Reporting Days total and average
- 7-day trend versus the previous 7 days
- All-time focused time
- Day-to-day focused-hours chart for 7, 14, or 30 days
- Best reporting day, longest session, active-day count, and derived non-focus time

Session Entry records contain Started At and Finished At. Non-Focus Time is derived
automatically from the elapsed session span minus Focused Time. Break data is not
stored.

VISUAL FRAMING
--------------
Visual framing is saved separately for each visual resource. In Application Settings,
select a Preview Preset and adjust:
- Fit Mode (Contain / Cover / Stretch)
- Crop Zoom
- Horizontal Crop
- Vertical Crop

The same framing is used by images, GIFs, videos, previews, and the Visual Companion.
Crop Zoom can be used to remove encoded black side areas from portrait/phone videos.

DEVELOPMENT AND RECORD SAFETY
-----------------------------
The application keeps its existing .cyndaquil JSON file formats and locations.
Each successful save retains the previous valid file as <filename>.bak. These
are rolling local backups, not a replacement for copying .cyndaquil to another
drive periodically. resources remains excluded from Git.

If an existing data file is unreadable or malformed, startup stops rather than
silently replacing it with empty records. Close Cyndaquil, copy the complete
.cyndaquil folder somewhere safe, and inspect the affected JSON file and its
.bak backup. Restore a verified backup manually only after preserving both files.

Code responsibilities:
- app.py: application startup and Qt initialization
- main.py: main window and session coordination
- navigation.py: sidebar, version display, and direct History/Statistics routes
- ui_helpers.py: shared input behavior and completion dialog
- instance.py: single-instance lock and activation
- persistence.py: validated JSON reads, atomic writes, and rolling backups
- store.py: settings, resources, presets, and Qt notification facade
- session_repository.py: transactional history and tag operations
- statistics_view.py / history_analytics.py: statistics UI and reporting calculations
- session.py: timing and session state
- remaining page/media modules: their respective UI and media responsibilities

Run regression checks with:
    python -m unittest discover -s tests -v

For headless Linux, set QT_QPA_PLATFORM=offscreen and
QT_AUDIO_BACKEND=pulseaudio before running the tests. Interactive desktop,
Windows tray integration, and audible playback require a desktop test.

HISTORY FILTERS AND TAGS
-----------------------
Session History and Statistics are available from the sidebar only. Session History
opens with all records and supports Today, Last 7/30/90 Days, or inclusive
custom dates. Dates use the existing Reporting Day Start setting. Undated
legacy records remain available in All time. Reset filters restores all records.

Add comma-separated tags when completing a session or editing a Session Entry.
Existing tags can be selected from the suggestions list. To label older records
in bulk, select rows with Ctrl/Shift, then right-click and choose Edit tags for
selected sessions... to add or remove tags. Bulk tagging leaves notes, timestamps, focused time, and other fields intact.

The tag filter includes or excludes sessions matching ANY entered tag, ignoring
case. It applies to both History views. Date filters affect Session History;
Statistics retains its own reporting windows within the selected tag group.
Filtering does not edit or delete records. Old sessions without tags work as before.

Completion notes are shown only in the selected-record reading pane, preserving
line breaks. The table keeps centered session details without a note column. Show timing details reveals the additional columns.
Distraction Dump is collapsed by default in the Session Entry editor and can be
expanded without changing its saved contents.

UPDATING AND IDENTIFYING THE RUNNING APP
--------------------------------------
Version 5.2.0 appears at the bottom of the sidebar. Session History and Statistics
are separate sidebar destinations. About Cyndaquil shows both the running version
and the application/data folders so you can confirm which copy is running.

After pulling an update, fully quit Cyndaquil using Quit Cyndaquil (save an active
session first), then launch Cyndaquil.pyw from the folder you updated. Closing the
window can leave the app running in the tray. To launch that exact file from its
folder in a Windows terminal, run:
    py -3 Cyndaquil.pyw

Generated Python caches are no longer committed. User media and new runtime files
are ignored by Git; previously tracked .cyndaquil records and backups are retained.
Developer architecture and check commands are in docs/DEVELOPMENT.md.

APPEARANCE
----------
The interface uses blue (#3a637b), slate (#63849d), bronze (#c4a46b),
cream (#ffefa5), and yellow (#ffde00), with darker blue surfaces for readable text.
History filters share one compact row. Tag suggestions appear while typing.
Completion notes use a separate padded card with a resizable gap below the table.
The media library, generated ambience, and custom branding are preserved.
