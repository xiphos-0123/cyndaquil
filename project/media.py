from __future__ import annotations

import random

from PySide6.QtCore import QObject, QRectF, QSizeF, Qt, QUrl, Signal
from PySide6.QtGui import QMovie, QPainter, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    from PySide6.QtMultimediaWidgets import QGraphicsVideoItem

    _HAS_GRAPHICS_VIDEO = True
except Exception:  # pragma: no cover - compatibility fallback
    QGraphicsVideoItem = None
    _HAS_GRAPHICS_VIDEO = False
    from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .store import Store


class AudioController(QObject):
    track_changed = Signal(str)
    availability_changed = Signal(bool)

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        self.output.setVolume(store.settings.get("audio_volume", 55) / 100)
        self.ids: list[str] = []
        self.index = -1
        self.shuffle = False
        self.loop = True
        self.player.mediaStatusChanged.connect(self._status_changed)

    def set_playlist(self, resource_ids: list[str], autoplay=True) -> None:
        valid = []
        for rid in resource_ids:
            path, _ = self.store.resolve_resource(rid)
            item = self.store.resource_by_id(rid)
            if path and item and item.get("kind") == "audio":
                valid.append(rid)
        self.ids = valid
        self.index = 0 if valid else -1
        self.availability_changed.emit(bool(valid))
        if valid:
            self._load_current(autoplay)
        else:
            self.player.stop()
            self.player.setSource(QUrl())

    def has_music(self) -> bool:
        return bool(self.ids)

    def current_name(self) -> str:
        if not (0 <= self.index < len(self.ids)):
            return ""
        item = self.store.resource_by_id(self.ids[self.index])
        return item.get("name", "") if item else ""

    def _load_current(self, autoplay: bool) -> None:
        if not (0 <= self.index < len(self.ids)):
            return
        path, _ = self.store.resolve_resource(self.ids[self.index])
        if not path:
            self.next()
            return
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.track_changed.emit(self.current_name())
        if autoplay:
            self.player.play()

    def toggle(self) -> None:
        if not self.ids:
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def next(self) -> None:
        if not self.ids:
            return
        if self.shuffle and len(self.ids) > 1:
            choices = [i for i in range(len(self.ids)) if i != self.index]
            self.index = random.choice(choices)
        else:
            self.index += 1
            if self.index >= len(self.ids):
                if not self.loop:
                    self.player.stop()
                    return
                self.index = 0
        self._load_current(True)

    def previous(self) -> None:
        if not self.ids:
            return
        self.index = (self.index - 1) % len(self.ids)
        self._load_current(True)

    def set_volume(self, value: int) -> None:
        self.output.setVolume(max(0, min(100, int(value))) / 100)

    def stop(self) -> None:
        self.player.stop()
        self.player.setSource(QUrl())
        self.ids = []
        self.index = -1

    def _status_changed(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next()


class MediaVisual(QWidget):
    """
    Unified visual renderer for images, GIFs, and video.

    Framing is resource-specific and supports:
    - Contain / Cover / Stretch
    - Crop Zoom (100-400%)
    - Horizontal / Vertical crop position (-100..100)

    The video path uses QGraphicsVideoItem when available so portrait and
    letterboxed videos can be zoomed and panned instead of being trapped in a
    fixed QVideoWidget rectangle.
    """

    FIT_MODES = {"contain", "cover", "stretch"}

    def __init__(self, store: Store, parent=None):
        super().__init__(parent)
        self.store = store
        self.stack = QStackedWidget(self)

        self.image = QLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setMinimumSize(1, 1)
        self.image.setScaledContents(False)
        self.image.setStyleSheet("background: #05090D;")

        self.video_view = None
        self.video_scene = None
        self.video_item = None
        self.video_widget = None

        if _HAS_GRAPHICS_VIDEO:
            self.video_scene = QGraphicsScene(self)
            self.video_view = QGraphicsView(self.video_scene)
            self.video_view.setFrameShape(QFrame.Shape.NoFrame)
            self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.video_view.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            self.video_view.setStyleSheet("background: #05090D; border: none;")
            self.video_item = QGraphicsVideoItem()
            self.video_item.setAspectRatioMode(Qt.AspectRatioMode.IgnoreAspectRatio)
            self.video_scene.addItem(self.video_item)
            try:
                self.video_item.nativeSizeChanged.connect(self._video_native_size_changed)
            except Exception:
                pass
            video_surface = self.video_view
        else:  # compatibility fallback; crop zoom is limited on this path
            self.video_widget = QVideoWidget()
            video_surface = self.video_widget

        self.player = QMediaPlayer(self)
        self.video_audio = QAudioOutput(self)
        self.video_audio.setVolume(0.0)
        self.player.setAudioOutput(self.video_audio)
        self.player.setVideoOutput(
            self.video_item if self.video_item is not None else self.video_widget
        )
        self.player.mediaStatusChanged.connect(self._video_status)

        self.stack.addWidget(self.image)
        self.stack.addWidget(video_surface)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self.movie: QMovie | None = None
        self.pixmap: QPixmap | None = None
        self.kind: str | None = None
        self.resource_id: str | None = None
        self.fit_mode = "contain"
        self.zoom = 100
        self.pan_x = 0
        self.pan_y = 0
        self._video_native = QSizeF(16, 9)
        self.setVisible(False)

        if hasattr(store, "visual_framing_changed"):
            store.visual_framing_changed.connect(self._framing_changed)

    def set_fit_mode(self, mode: str) -> None:
        self.set_framing(fit=mode)

    def set_framing(
        self,
        fit: str | None = None,
        zoom: int | None = None,
        pan_x: int | None = None,
        pan_y: int | None = None,
    ) -> None:
        if fit is not None:
            self.fit_mode = fit if fit in self.FIT_MODES else "contain"
        if zoom is not None:
            self.zoom = max(100, min(400, int(zoom)))
        if pan_x is not None:
            self.pan_x = max(-100, min(100, int(pan_x)))
        if pan_y is not None:
            self.pan_y = max(-100, min(100, int(pan_y)))
        self._refresh_current()

    def _load_stored_framing(self, resource_id: str | None) -> None:
        framing = (
            self.store.visual_framing(resource_id) if hasattr(self.store, "visual_framing") else {}
        )
        self.fit_mode = framing.get("fit", "contain")
        self.zoom = int(framing.get("zoom", 100))
        self.pan_x = int(framing.get("pan_x", 0))
        self.pan_y = int(framing.get("pan_y", 0))

    def _framing_changed(self, resource_id: str) -> None:
        if self.resource_id and str(self.resource_id) == str(resource_id):
            self._load_stored_framing(self.resource_id)
            self._refresh_current()

    def source_aspect_ratio(self) -> float | None:
        if self.kind == "image" and self.pixmap and not self.pixmap.isNull():
            if self.pixmap.height() > 0:
                return self.pixmap.width() / self.pixmap.height()
        if self.kind == "gif" and self.movie:
            pix = self.movie.currentPixmap()
            if not pix.isNull() and pix.height() > 0:
                return pix.width() / pix.height()
            size = self.movie.frameRect().size()
            if size.height() > 0:
                return size.width() / size.height()
        if self.kind == "video":
            size = self._video_native
            if size.height() > 0:
                return size.width() / size.height()
        return None

    def set_resource(self, resource_id: str | None) -> bool:
        if resource_id == self.resource_id and self.kind is not None:
            self._load_stored_framing(resource_id)
            self.setVisible(True)
            self._refresh_current()
            return True

        self.stop()
        self.resource_id = resource_id
        path, _ = self.store.resolve_resource(resource_id)
        item = self.store.resource_by_id(resource_id)
        if not path or not item or item.get("kind") not in {"image", "gif", "video"}:
            self.resource_id = resource_id
            self.setVisible(False)
            return False

        self._load_stored_framing(resource_id)
        self.kind = item.get("kind")

        if self.kind == "image":
            self.pixmap = QPixmap(str(path))
            self.stack.setCurrentWidget(self.image)
            self._refresh_pixmap()
        elif self.kind == "gif":
            self.movie = QMovie(str(path))
            self.movie.frameChanged.connect(self._refresh_movie)
            self.movie.start()
            self.stack.setCurrentWidget(self.image)
            self._refresh_movie()
        else:
            surface = self.video_view if self.video_view is not None else self.video_widget
            self.stack.setCurrentWidget(surface)
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
            self._layout_video()

        self.setVisible(True)
        return True

    def stop(self) -> None:
        if self.movie:
            try:
                self.movie.frameChanged.disconnect(self._refresh_movie)
            except Exception:
                pass
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None
        self.player.stop()
        self.player.setSource(QUrl())
        self.image.clear()
        self.pixmap = None
        self.kind = None
        self._video_native = QSizeF(16, 9)

    def _video_status(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.player.setPosition(0)
            self.player.play()

    def _video_native_size_changed(self, size: QSizeF) -> None:
        if size.width() > 0 and size.height() > 0:
            self._video_native = QSizeF(size)
        self._layout_video()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_current()

    def _refresh_current(self) -> None:
        if self.kind == "image":
            self._refresh_pixmap()
        elif self.kind == "gif":
            self._refresh_movie()
        elif self.kind == "video":
            self._layout_video()

    def _geometry_for_source(self, sw: float, sh: float, tw: float, th: float):
        if sw <= 0 or sh <= 0 or tw <= 0 or th <= 0:
            return 0.0, 0.0, 1.0, 1.0

        if self.fit_mode == "stretch":
            dw, dh = tw, th
        else:
            contain_scale = min(tw / sw, th / sh)
            cover_scale = max(tw / sw, th / sh)
            base = cover_scale if self.fit_mode == "cover" else contain_scale
            dw, dh = sw * base, sh * base

        zoom_scale = self.zoom / 100.0
        dw *= zoom_scale
        dh *= zoom_scale

        overflow_x = max(0.0, dw - tw)
        overflow_y = max(0.0, dh - th)
        x = (tw - dw) / 2.0 - (self.pan_x / 100.0) * (overflow_x / 2.0)
        y = (th - dh) / 2.0 - (self.pan_y / 100.0) * (overflow_y / 2.0)
        return x, y, dw, dh

    def _render_pixmap(self, source: QPixmap) -> QPixmap | None:
        if source.isNull():
            return None
        target = self.image.size()
        tw, th = target.width(), target.height()
        if tw <= 0 or th <= 0:
            return None

        canvas = QPixmap(tw, th)
        canvas.fill(Qt.GlobalColor.transparent)
        x, y, dw, dh = self._geometry_for_source(source.width(), source.height(), tw, th)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawPixmap(QRectF(x, y, dw, dh), source, QRectF(source.rect()))
        painter.end()
        return canvas

    def _refresh_movie(self, *args) -> None:
        if not self.movie:
            return
        shown = self._render_pixmap(self.movie.currentPixmap())
        if shown is not None:
            self.image.setPixmap(shown)

    def _refresh_pixmap(self) -> None:
        if not self.pixmap or self.pixmap.isNull():
            return
        shown = self._render_pixmap(self.pixmap)
        if shown is not None:
            self.image.setPixmap(shown)

    def _layout_video(self) -> None:
        if (
            self.video_item is not None
            and self.video_view is not None
            and self.video_scene is not None
        ):
            viewport = self.video_view.viewport().size()
            tw, th = max(1, viewport.width()), max(1, viewport.height())
            sw = self._video_native.width() if self._video_native.width() > 0 else 16
            sh = self._video_native.height() if self._video_native.height() > 0 else 9
            x, y, dw, dh = self._geometry_for_source(sw, sh, tw, th)
            self.video_scene.setSceneRect(0, 0, tw, th)
            self.video_item.setSize(QSizeF(dw, dh))
            self.video_item.setPos(x, y)
        elif self.video_widget is not None:
            # Fallback path: cover/contain works, but arbitrary pan/zoom requires
            # QGraphicsVideoItem and is therefore unavailable on very old Qt builds.
            try:
                if self.fit_mode == "stretch":
                    mode = Qt.AspectRatioMode.IgnoreAspectRatio
                elif self.fit_mode == "cover" or self.zoom > 100:
                    mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
                else:
                    mode = Qt.AspectRatioMode.KeepAspectRatio
                self.video_widget.setAspectRatioMode(mode)
            except Exception:
                pass
