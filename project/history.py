"""Session browsing, read-only filters, and productivity statistics."""

from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QDate, QItemSelectionModel, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .history_filters import filter_sessions, normalize_tags
from .history_records import _session_nonfocus_seconds, _session_span_seconds, _short_datetime
from .persistence import PersistenceError
from .session_entry import SessionEntryDialog
from .statistics_view import StatisticsView
from .store import Store
from .tag_editor import BulkTagDialog, TagEditor, available_tags
from .utils import (
    current_reporting_day,
    format_seconds,
    parse_iso_datetime,
)


class HistoryPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel("History & Productivity")
        title.setObjectName("Title")
        root.addWidget(title)
        tag_controls = QHBoxLayout()
        tag_controls.addWidget(QLabel("Tag filter"))
        self.tag_filter = TagEditor(available=available_tags(store.sessions))
        self.tag_filter.text.setAccessibleName("Filter sessions by tags")
        self.tag_filter.add.setText("Add filter")
        self.tag_mode = QComboBox()
        self.tag_mode.addItem("Include any", "include")
        self.tag_mode.addItem("Exclude any", "exclude")
        tag_controls.addWidget(self.tag_mode)
        tag_controls.addWidget(self.tag_filter, 1)
        root.addLayout(tag_controls)
        tag_hint = QLabel(
            "Leave tags empty to show everything. Tag filters apply to both views; dates below filter Session History."
        )
        tag_hint.setObjectName("Muted")
        tag_hint.setWordWrap(True)
        root.addWidget(tag_hint)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        history_view = QWidget()
        history_layout = QVBoxLayout(history_view)
        stats_scroll = QScrollArea()
        stats_scroll.setWidgetResizable(True)
        stats_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.statistics = StatisticsView(store)
        stats_scroll.setWidget(self.statistics)
        self.tabs.addTab(history_view, "Session History")
        self.tabs.addTab(stats_scroll, "Statistics")

        dates = QHBoxLayout()
        dates.addWidget(QLabel("Show"))
        self.period = QComboBox()
        for label, days in (
            ("All time", 0),
            ("Today", 1),
            ("Last 7 days", 7),
            ("Last 30 days", 30),
            ("Last 90 days", 90),
            ("Custom dates", -1),
        ):
            self.period.addItem(label, days)
        dates.addWidget(self.period)
        self.from_date = QDateEdit(QDate.currentDate().addDays(-6))
        self.to_date = QDateEdit(QDate.currentDate())
        for editor in (self.from_date, self.to_date):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd MMM yyyy")
        self.date_range_controls = QWidget()
        date_range = QHBoxLayout(self.date_range_controls)
        date_range.setContentsMargins(0, 0, 0, 0)
        date_range.addWidget(QLabel("From"))
        date_range.addWidget(self.from_date)
        date_range.addWidget(QLabel("Through"))
        date_range.addWidget(self.to_date)
        date_range.addStretch()
        dates.addStretch()
        self.clear_filters = QPushButton("Reset filters")
        dates.addWidget(self.clear_filters)
        history_layout.addLayout(dates)
        history_layout.addWidget(self.date_range_controls)
        self.date_range_controls.hide()
        self.result_count = QLabel()
        self.result_count.setObjectName("Muted")
        history_layout.addWidget(self.result_count)

        buttons = QHBoxLayout()
        self.open_entry = QPushButton("Open Session Entry…")
        self.open_entry.setObjectName("Primary")
        self.delete = QPushButton("Delete Session")
        self.delete.setObjectName("Danger")
        buttons.addWidget(self.open_entry)
        self.tag_selected = QAction("Edit tags for selected sessions…", self)
        self.show_details = QCheckBox("Show timing details")
        self.show_details.toggled.connect(self._set_timing_details)
        buttons.addWidget(self.show_details)
        buttons.addStretch()
        buttons.addWidget(self.delete)
        history_layout.addLayout(buttons)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "Started",
                "Finished",
                "Session Objective",
                "Mode",
                "Session Span",
                "Focused",
                "Non-Focus",
                "Preset",
                "Tags",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_session_menu)
        self.table.setToolTip("Select rows with Ctrl/Shift; right-click to edit their tags.")
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._set_timing_details(False)
        self.session_splitter = QSplitter(Qt.Orientation.Vertical)
        self.session_splitter.setChildrenCollapsible(False)
        self.session_splitter.addWidget(self.table)
        self.note_detail = QPlainTextEdit()
        self.note_detail.setReadOnly(True)
        self.note_detail.setPlaceholderText("Select a session to read its complete notes here.")
        self.note_detail.setAccessibleName("Selected session completion notes")
        self.note_detail.setMinimumHeight(70)
        note_pane = QWidget()
        note_layout = QVBoxLayout(note_pane)
        note_layout.setContentsMargins(0, 0, 0, 0)
        self.note_title = QLabel("Completion Notes · Select a session")
        self.note_title.setTextFormat(Qt.TextFormat.PlainText)
        self.note_title.setWordWrap(True)
        note_layout.addWidget(self.note_title)
        note_layout.addWidget(self.note_detail)
        self.session_splitter.addWidget(note_pane)
        self.session_splitter.setStretchFactor(0, 1)
        self.session_splitter.setStretchFactor(1, 0)
        self.session_splitter.setSizes([500, 130])
        history_layout.addWidget(self.session_splitter, 1)
        self.period.currentIndexChanged.connect(self._filters_changed)
        self.from_date.dateChanged.connect(self._filters_changed)
        self.to_date.dateChanged.connect(self._filters_changed)
        self.tag_filter.changed.connect(self.refresh)
        self.tag_mode.currentIndexChanged.connect(self.refresh)
        self.clear_filters.clicked.connect(self._reset_filters)
        self.from_date.setEnabled(False)
        self.to_date.setEnabled(False)

        self.tag_selected.triggered.connect(self.tag_selected_entries)
        self.open_entry.clicked.connect(self.open_selected_entry)
        self.delete.clicked.connect(self.delete_entry)
        self.table.cellDoubleClicked.connect(lambda row, column: self.open_selected_entry())
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.store.sessions_changed.connect(self.refresh)
        self.store.settings_changed.connect(self.refresh)
        self.refresh()

    def _set_timing_details(self, visible):
        for column in (1, 3, 4, 6, 7):
            self.table.setColumnHidden(column, not visible)

    def _tagged_sessions(self):
        return filter_sessions(
            self.store.sessions, tags=self.tag_filter.tags(), tag_mode=self.tag_mode.currentData()
        )

    def _history_sessions(self):
        days = self.period.currentData()
        start = end = None
        if days == -1:
            start = self.from_date.date().toPython()
            end = self.to_date.date().toPython()
            if start > end:
                return []
        elif days:
            end = current_reporting_day(int(self.store.settings.get("history_day_start_hour", 0)))
            start = end - timedelta(days=days - 1)
        return filter_sessions(
            self._tagged_sessions(),
            start=start,
            end=end,
            start_hour=int(self.store.settings.get("history_day_start_hour", 0)),
        )

    def _filters_changed(self, *args):
        custom = self.period.currentData() == -1
        self.date_range_controls.setVisible(custom)
        self.from_date.setEnabled(custom)
        self.to_date.setEnabled(custom)
        self.refresh()

    def _reset_filters(self):
        self.period.setCurrentIndex(0)
        self.tag_filter.text.clear()
        self.tag_mode.setCurrentIndex(0)
        self.refresh()

    def _selection_changed(self):
        self._update_actions()
        session = self.selected_session()
        self.note_detail.setPlainText((session.get("completion_note", "") or "") if session else "")
        if session:
            objective = session.get("mission") or session.get("preset_name") or "Focus session"
            self.note_title.setText(
                f"Completion Notes · {objective} · {_short_datetime(session.get('started_at'))}"
            )
            self.note_detail.setPlaceholderText("This session has no completion notes.")
        else:
            multiple = len(self.selected_ids()) > 1
            self.note_title.setText(
                "Completion Notes · Multiple sessions selected"
                if multiple
                else "Completion Notes · Select a session"
            )
            self.note_detail.setPlaceholderText(
                "Select one session to read its complete notes here."
            )

    def refresh(self) -> None:
        selected = set(self.selected_ids())
        self.table.setRowCount(0)
        selected_rows = []

        self.tag_filter.set_available(available_tags(self.store.sessions))
        sessions = self._history_sessions()
        invalid_dates = (
            self.period.currentData() == -1 and self.from_date.date() > self.to_date.date()
        )
        self.result_count.setText(
            "Choose a From date on or before Through."
            if invalid_dates
            else f"{len(sessions)} of {len(self.store.sessions)} sessions · Newest first · Dates use the reporting-day boundary"
        )

        def started_timestamp(session):
            started = parse_iso_datetime(session.get("started_at"))
            return started.timestamp() if started else float("-inf")

        for session in sorted(sessions, key=started_timestamp, reverse=True):
            row = self.table.rowCount()
            self.table.insertRow(row)
            span = _session_span_seconds(session)
            nonfocus = _session_nonfocus_seconds(session)
            values = [
                _short_datetime(session.get("started_at")),
                _short_datetime(session.get("ended_at")),
                session.get("mission", ""),
                str(session.get("mode", "")).title(),
                format_seconds(span) if span is not None else "—",
                format_seconds(session.get("focused_seconds", 0)),
                format_seconds(nonfocus) if nonfocus is not None else "—",
                session.get("preset_name", ""),
                ", ".join(normalize_tags(session.get("tags", []))),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, session.get("id"))
                if col == 6:
                    item.setToolTip("Derived automatically: Session Span minus Focused Time")
                self.table.setItem(row, col, item)
            if session.get("id") in selected:
                selected_rows.append(row)

        for column, width in enumerate((145, 145, 200, 90, 100, 100, 100, 140, 180)):
            self.table.setColumnWidth(column, width)
        self.table.resizeRowsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        for row in selected_rows:
            self.table.selectionModel().select(
                self.table.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
            )
        self.statistics.refresh(self._tagged_sessions())
        self._selection_changed()

    def selected_ids(self):
        return [
            self.table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole)
            for index in self.table.selectionModel().selectedRows()
            if self.table.item(index.row(), 0)
        ]

    def selected_id(self):
        ids = self.selected_ids()
        return ids[0] if len(ids) == 1 else None

    def _show_session_menu(self, position):
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        selected_rows = {item.row() for item in self.table.selectionModel().selectedRows()}
        if index.row() not in selected_rows:
            self.table.clearSelection()
            self.table.selectRow(index.row())
        menu = QMenu(self)
        count = len(self.selected_ids())
        self.tag_selected.setText(
            f"Edit tags for {count} selected session{'s' if count != 1 else ''}…"
        )
        menu.addAction(self.tag_selected)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def tag_selected_entries(self):
        ids = self.selected_ids()
        if not ids:
            return
        dialog = BulkTagDialog(len(ids), available_tags(self.store.sessions), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.store.update_session_tags(
                    ids, dialog.editor.tags(), remove=dialog.mode.currentData()
                )
            except PersistenceError as error:
                QMessageBox.critical(self, "Tags Were Not Saved", str(error))

    def selected_session(self):
        return self.store.session_by_id(self.selected_id())

    def _update_actions(self) -> None:
        selected = self.selected_id() is not None
        self.open_entry.setEnabled(selected)
        self.delete.setEnabled(selected)
        self.tag_selected.setEnabled(bool(self.selected_ids()))

    def open_selected_entry(self) -> None:
        session = self.selected_session()
        if session:
            SessionEntryDialog(self.store, session, self).exec()

    def delete_entry(self) -> None:
        sid = self.selected_id()
        if (
            sid
            and QMessageBox.question(
                self,
                "Delete Session",
                "Delete the selected session permanently?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                self.store.delete_session(sid)
            except PersistenceError as error:
                QMessageBox.critical(self, "Session Was Not Deleted", str(error))
