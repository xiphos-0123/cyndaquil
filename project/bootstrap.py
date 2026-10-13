from __future__ import annotations

import ctypes
import math
import os
import random
import shutil
import wave
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen


AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"}
VISUAL_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v"}


def hide_folder_windows(path: Path) -> None:
    if os.name != "nt":
        return
    try:
        hidden = 0x02
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != 0xFFFFFFFF:
            ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs | hidden)
    except Exception:
        pass


def _generate_fallback_icon(path: Path) -> None:
    """Generate a simple runtime-only ember mark. No Explorer/file icon is created."""
    image = QImage(256, 256, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # C-shaped navy body.
    c = QPainterPath()
    c.moveTo(183, 68)
    c.cubicTo(160, 43, 121, 38, 88, 54)
    c.cubicTo(54, 71, 35, 105, 40, 142)
    c.cubicTo(45, 183, 77, 214, 118, 217)
    c.cubicTo(145, 219, 170, 208, 187, 188)

    pen = QPen(QColor("#153247"), 48)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPath(c)

    # One restrained flame accent at the open side.
    flame = QPainterPath()
    flame.moveTo(181, 83)
    flame.cubicTo(207, 70, 213, 46, 199, 25)
    flame.cubicTo(190, 42, 176, 40, 169, 22)
    flame.cubicTo(161, 49, 162, 71, 181, 83)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#E86B34"))
    painter.drawPath(flame)

    inner = QPainterPath()
    inner.moveTo(183, 69)
    inner.cubicTo(195, 60, 197, 49, 191, 41)
    inner.cubicTo(186, 50, 178, 49, 174, 41)
    inner.cubicTo(171, 54, 173, 64, 183, 69)
    painter.setBrush(QColor("#F5C24B"))
    painter.drawPath(inner)

    painter.end()
    image.save(str(path), "PNG")


def _generate_default_visual(path: Path) -> None:
    """Generate a quiet ember/campfire visual for the permanent Default preset."""
    w, h = 1280, 720
    image = QImage(w, h, QImage.Format.Format_ARGB32)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    gradient = QLinearGradient(0, 0, 0, h)
    gradient.setColorAt(0.0, QColor("#08121A"))
    gradient.setColorAt(0.55, QColor("#102433"))
    gradient.setColorAt(1.0, QColor("#182B36"))
    painter.fillRect(0, 0, w, h, gradient)

    # Ground glow.
    painter.setPen(Qt.PenStyle.NoPen)
    for radius, alpha in [(240, 18), (175, 28), (120, 42)]:
        color = QColor("#E86B34")
        color.setAlpha(alpha)
        painter.setBrush(color)
        painter.drawEllipse(w // 2 - radius, h - 220 - radius // 2, radius * 2, radius)

    # Logs.
    log_pen = QPen(QColor("#5B3B2A"), 34)
    log_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(log_pen)
    painter.drawLine(w // 2 - 82, h - 128, w // 2 + 78, h - 88)
    painter.drawLine(w // 2 - 78, h - 88, w // 2 + 82, h - 128)

    # Flame body.
    painter.setPen(Qt.PenStyle.NoPen)
    outer = QPainterPath()
    outer.moveTo(w // 2, h - 335)
    outer.cubicTo(w // 2 - 75, h - 248, w // 2 - 58, h - 151, w // 2, h - 105)
    outer.cubicTo(w // 2 + 76, h - 157, w // 2 + 72, h - 244, w // 2 + 28, h - 287)
    outer.cubicTo(w // 2 + 10, h - 304, w // 2 + 7, h - 324, w // 2, h - 335)
    painter.setBrush(QColor("#E86B34"))
    painter.drawPath(outer)

    inner = QPainterPath()
    inner.moveTo(w // 2 + 3, h - 260)
    inner.cubicTo(w // 2 - 37, h - 210, w // 2 - 29, h - 155, w // 2 + 1, h - 130)
    inner.cubicTo(w // 2 + 40, h - 163, w // 2 + 34, h - 216, w // 2 + 14, h - 239)
    painter.setBrush(QColor("#F5C24B"))
    painter.drawPath(inner)

    # Deterministic embers.
    rng = random.Random(179)
    for _ in range(36):
        x = w // 2 + rng.randint(-135, 135)
        y = h - rng.randint(245, 520)
        r = rng.randint(2, 6)
        color = QColor("#F6A447" if rng.random() < 0.55 else "#E86B34")
        color.setAlpha(rng.randint(80, 190))
        painter.setBrush(color)
        painter.drawEllipse(x - r, y - r, r * 2, r * 2)

    painter.end()
    image.save(str(path), "PNG")


def _generate_default_audio(path: Path) -> None:
    """Generate a gentle, loopable synthetic ember ambience WAV."""
    sample_rate = 22050
    duration = 18
    frame_count = sample_rate * duration
    rng = random.Random(217)

    # Low-frequency smoothed noise + sparse crackles. The amplitude is
    # intentionally conservative so the fallback is ambience, not music.
    smooth = 0.0
    crackle = 0.0

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)

        frames = bytearray()
        for i in range(frame_count):
            target = rng.uniform(-1.0, 1.0)
            smooth = smooth * 0.997 + target * 0.003

            if rng.random() < 0.0008:
                crackle += rng.uniform(-0.55, 0.55)
            crackle *= 0.985

            # Very soft warm hum prevents absolute digital silence between pops.
            hum = 0.020 * math.sin(2 * math.pi * 82 * (i / sample_rate))
            value = smooth * 0.13 + crackle * 0.20 + hum
            value = max(-0.25, min(0.25, value))
            sample = int(value * 32767)
            frames.extend(int(sample).to_bytes(2, byteorder="little", signed=True))

        wav.writeframes(frames)


def ensure_system_assets(data_dir: Path) -> dict[str, Path]:
    generated = data_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)

    icon = generated / "fallback_icon.png"
    visual = generated / "fallback_visual.png"
    audio = generated / "fallback_audio.wav"

    if not icon.exists():
        _generate_fallback_icon(icon)
    if not visual.exists():
        _generate_default_visual(visual)
    if not audio.exists():
        _generate_default_audio(audio)

    return {"icon": icon, "visual": visual, "audio": audio}


def replace_managed_asset(source: Path, destination_dir: Path, stem: str, allowed_exts: set[str]) -> Path:
    source = Path(source).resolve()
    if source.suffix.lower() not in allowed_exts:
        raise ValueError(f"Unsupported file type: {source.suffix}")

    destination_dir.mkdir(parents=True, exist_ok=True)
    for old in destination_dir.glob(f"{stem}.*"):
        try:
            old.unlink()
        except OSError:
            pass

    destination = destination_dir / f"{stem}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    return destination


def runtime_icon(path: Path) -> QIcon:
    return QIcon(str(path))


def set_windows_app_id(app_id: str = "Cyndaquil.Productivity") -> None:
    """Improve taskbar identity without modifying any files or Explorer associations."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass
