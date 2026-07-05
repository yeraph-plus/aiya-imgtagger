from pathlib import Path

from PyQt6.QtGui import QPixmap, QPixmapCache
from PyQt6.QtCore import Qt

from config import THUMB_SIZE


def load_pixmap(path: Path, max_width: int = 0, max_height: int = 0) -> QPixmap | None:
    try:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return None
        if max_width > 0 and max_height > 0:
            pixmap = pixmap.scaled(
                max_width, max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        return pixmap
    except Exception:
        return None


def load_thumbnail(path: Path, size: int = THUMB_SIZE) -> QPixmap | None:
    key = f"{path.resolve()}_{size}"
    pixmap = QPixmapCache.find(key)
    if pixmap is not None and not pixmap.isNull():
        return pixmap

    pixmap = load_pixmap(path, size, size)
    if pixmap:
        QPixmapCache.insert(key, pixmap)
    return pixmap
