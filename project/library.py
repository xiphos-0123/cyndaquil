from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .store import Store
from .utils import reveal_path


class ResourcesPage(QWidget):
    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(12)

        title = QLabel("Resource Library")
        title.setObjectName("Title")

        info = QLabel(
            "Supported media placed anywhere inside the resources folder is added automatically. "
            "If an internally managed file is removed, its library entry is removed as well. "
            "External resources remain in the library when their original file is missing so they can be relinked."
        )
        info.setWordWrap(True)
        info.setObjectName("Muted")

        self.import_primary = QCheckBox("Copy imported files into the internal Resource Library")
        self.keep_backup = QCheckBox("Keep a local backup for externally linked files")

        controls = QHBoxLayout()
        self.add_btn = QPushButton("Import Files…")
        self.relink_btn = QPushButton("Relink Resource…")
        self.backup_btn = QPushButton("Create Backup")
        self.scan_btn = QPushButton("Scan Resource Library")
        self.reveal_btn = QPushButton("Show in Folder")
        self.remove_btn = QPushButton("Remove Resource")
        self.remove_btn.setObjectName("Danger")

        for button in (
            self.add_btn,
            self.relink_btn,
            self.backup_btn,
            self.scan_btn,
            self.reveal_btn,
        ):
            controls.addWidget(button)
        controls.addStretch()
        controls.addWidget(self.remove_btn)

        self.scan_status = QLabel("")
        self.scan_status.setObjectName("Muted")

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Name",
                "Type",
                "Source",
                "Status",
                "Backup",
                "Filename",
                "Primary Location",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setMinimumSectionSize(48)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.verticalHeader().setMinimumWidth(48)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(title)
        root.addWidget(info)
        root.addWidget(self.import_primary)
        root.addWidget(self.keep_backup)
        root.addLayout(controls)
        root.addWidget(self.scan_status)
        root.addWidget(self.table, 1)

        self.import_primary.toggled.connect(
            lambda checked: self.keep_backup.setEnabled(not checked)
        )
        self.add_btn.clicked.connect(self.add_files)
        self.relink_btn.clicked.connect(self.relink)
        self.backup_btn.clicked.connect(self.make_backup)
        self.scan_btn.clicked.connect(self.scan)
        self.reveal_btn.clicked.connect(self.reveal)
        self.remove_btn.clicked.connect(self.remove)
        self.table.itemSelectionChanged.connect(self._update_actions)

        store.resources_changed.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        selected = self.selected_id()
        self.table.setRowCount(0)

        for resource in self.store.resources:
            row = self.table.rowCount()
            self.table.insertRow(row)

            rid = resource.get("id")
            primary = self.store._path(resource.get("primary_path"))
            backup = self.store._path(resource.get("backup_path"))

            if resource.get("system_default"):
                source = "System Default"
            elif resource.get("managed"):
                source = "Internal"
            else:
                source = "External"

            values = [
                resource.get("name", ""),
                resource.get("kind", "").title(),
                source,
                self.store.resource_status(rid),
                "Yes" if backup and backup.exists() else "No",
                resource.get("filename", ""),
                str(primary or resource.get("primary_path", "")),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setData(Qt.ItemDataRole.UserRole, rid)
                self.table.setItem(row, col, item)

            if rid == selected:
                self.table.selectRow(row)

        self.table.resizeColumnsToContents()
        self._update_actions()

    def selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selected_resource(self):
        return self.store.resource_by_id(self.selected_id())

    def _update_actions(self) -> None:
        resource = self.selected_resource()
        exists = resource is not None
        special = bool(resource and resource.get("special"))
        external = bool(resource and not resource.get("managed") and not special)

        self.relink_btn.setEnabled(exists and not special)
        self.backup_btn.setEnabled(external)
        self.reveal_btn.setEnabled(exists)
        self.remove_btn.setEnabled(exists and not special)

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Resources",
            "",
            "Media (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.png *.jpg *.jpeg *.bmp *.webp *.gif *.mp4 *.mkv *.mov *.avi *.webm *.m4v);;All Files (*.*)",
        )

        for value in paths:
            try:
                self.store.add_resource(
                    Path(value),
                    import_primary=self.import_primary.isChecked(),
                    keep_backup=(
                        self.keep_backup.isChecked() and not self.import_primary.isChecked()
                    ),
                )
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Resource Import Failed",
                    f"{value}\n\n{exc}",
                )

    def relink(self) -> None:
        resource = self.selected_resource()
        if not resource or resource.get("special"):
            return

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Relink Resource",
        )
        if path:
            self.store.relink_resource(resource.get("id"), Path(path))

    def make_backup(self) -> None:
        rid = self.selected_id()
        if not rid:
            return

        if self.store.make_backup(rid):
            QMessageBox.information(
                self,
                "Backup Created",
                "A local backup was created in resources/backups.",
            )
        else:
            QMessageBox.warning(
                self,
                "Backup Failed",
                "Cyndaquil could not locate a usable source file for this resource.",
            )

    def scan(self) -> None:
        result = self.store.repair_resources()
        self.scan_status.setText(
            "Scan Complete — "
            f"Added {result['added']}, Removed {result['removed']}, "
            f"Relinked {result['repaired']}"
        )
        QTimer.singleShot(3500, self.scan_status.clear)

    def reveal(self) -> None:
        rid = self.selected_id()
        path, _ = self.store.resolve_resource(rid)
        if path:
            reveal_path(path)
        else:
            QMessageBox.information(
                self,
                "Resource Missing",
                "No working primary or backup file is currently available.",
            )

    def remove(self) -> None:
        resource = self.selected_resource()
        if not resource or resource.get("special"):
            return

        if (
            QMessageBox.question(
                self,
                "Remove Resource",
                f"Remove “{resource.get('name', '')}” from the Resource Library?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        delete_local = False
        if resource.get("managed") or resource.get("backup_path"):
            delete_local = (
                QMessageBox.question(
                    self,
                    "Delete Local Files",
                    "Also delete Cyndaquil-managed copies stored inside the resources folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )

        self.store.remove_resource(resource.get("id"), delete_local_files=delete_local)
