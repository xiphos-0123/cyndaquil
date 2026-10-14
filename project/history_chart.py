"""Focused-time chart rendering."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class DailyProgressChart(QWidget):
    """Focused-hours bars with a rolling seven-day trend line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values: list[tuple[date, int]] = []
        self.average = 0.0
        self.rolling: list[float] = []
        self.setMinimumHeight(250)

    def set_data(self, values: list[tuple[date, int]]) -> None:
        self.values = list(values)
        self.average = (
            sum(seconds for _, seconds in self.values) / len(self.values) if self.values else 0.0
        )
        self.rolling = []
        raw = [seconds for _, seconds in self.values]
        for index in range(len(raw)):
            start = max(0, index - 6)
            window = raw[start : index + 1]
            self.rolling.append(sum(window) / len(window))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(48, 18, -18, -36)
        if rect.width() <= 10 or rect.height() <= 10:
            return

        painter.setPen(QColor("#60788A"))
        if not self.values:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No session data yet")
            return

        max_seconds = max(
            max(v for _, v in self.values),
            max(self.rolling, default=0),
            3600,
        )
        max_hours = max(1, int((max_seconds + 3599) // 3600))
        max_seconds = max_hours * 3600

        for i in range(5):
            y = rect.bottom() - rect.height() * i / 4
            painter.setPen(QPen(QColor("#274052"), 1))
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            hours = max_hours * i / 4
            painter.setPen(QColor("#8EA4B3"))
            painter.drawText(2, int(y) - 8, 42, 16, Qt.AlignmentFlag.AlignRight, f"{hours:g}h")

        count = len(self.values)
        slot = rect.width() / max(1, count)
        bar_width = max(3.0, min(32.0, slot * 0.58))

        for index, (day, seconds) in enumerate(self.values):
            ratio = seconds / max_seconds if max_seconds else 0
            height = rect.height() * ratio
            x = rect.left() + slot * index + (slot - bar_width) / 2
            y = rect.bottom() - height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#E66C35") if seconds else QColor("#294A60"))
            painter.drawRoundedRect(QRectF(x, y, bar_width, max(2, height)), 3, 3)

            label_every = 1 if count <= 14 else 3 if count <= 35 else 7
            if index % label_every == 0 or index == count - 1:
                painter.setPen(QColor("#8EA4B3"))
                painter.drawText(
                    int(x - slot * 0.25),
                    rect.bottom() + 7,
                    int(bar_width + slot * 0.5),
                    20,
                    Qt.AlignmentFlag.AlignHCenter,
                    day.strftime("%d %b"),
                )

        # Selected-window average.
        if self.average > 0:
            avg_y = rect.bottom() - rect.height() * (self.average / max_seconds)
            painter.setPen(QPen(QColor("#FFD16A"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(rect.left(), int(avg_y), rect.right(), int(avg_y))

        # Rolling 7-day average. For the first six points, this uses all
        # available days so the progression starts immediately.
        if self.rolling:
            painter.setPen(QPen(QColor("#F7E9C8"), 2))
            previous = None
            for index, seconds in enumerate(self.rolling):
                x = rect.left() + slot * index + slot / 2
                y = rect.bottom() - rect.height() * (seconds / max_seconds)
                point = (int(x), int(y))
                if previous is not None:
                    painter.drawLine(previous[0], previous[1], point[0], point[1])
                previous = point

        painter.setPen(QColor("#FFD16A"))
        painter.drawText(
            rect.right() - 150, rect.top(), 150, 18, Qt.AlignmentFlag.AlignRight, "— window average"
        )
        painter.setPen(QColor("#F7E9C8"))
        painter.drawText(
            rect.right() - 150,
            rect.top() + 18,
            150,
            18,
            Qt.AlignmentFlag.AlignRight,
            "— rolling 7-day average",
        )
