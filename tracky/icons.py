"""Icon resolution for applications, websites, and user overrides."""

from __future__ import annotations

# shutil copies user-selected icons, Path keeps paths readable, and quote safely
# places a website URL inside the favicon service query string.
import shutil
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QFileInfo, QObject, QUrl, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QFileIconProvider

from .database import Database
from .utils import app_data_dir, safe_icon_filename


class IconManager(QObject):
    """Resolve native process icons and asynchronously cache website favicons."""

    icon_ready = Signal(str)

    def __init__(self, database: Database, parent=None) -> None:
        super().__init__(parent)
        self.database = database
        self.provider = QFileIconProvider()
        self.network = QNetworkAccessManager(self)
        self._pending: dict[QNetworkReply, tuple[str, str, int]] = {}

    def icon_for(self, entity: dict) -> QIcon:
        key = entity["entity_key"]

        # A user-selected icon always wins over automatic sources.
        custom = entity.get("custom_icon")
        if custom and Path(custom).exists():
            return QIcon(custom)

        if key.startswith("web:"):
            cached = self._favicon_path(key)
            if cached.exists():
                return QIcon(str(cached))
            self._request_favicon(key)
            return self._letter_icon(key.removeprefix("web:")[:1].upper() or "W")

        process_path = entity.get("process_path")
        if process_path and Path(process_path).exists():
            # QFileIconProvider asks the Windows shell for the real executable
            # icon, so there is no need for a separate native icon-extraction DLL.
            icon = self.provider.icon(QFileInfo(process_path))
            if not icon.isNull():
                return icon

        name = entity.get("process_name") or "A"
        return self._letter_icon(name[:1].upper())

    def save_custom_icon(self, entity_key: str, source_path: str) -> str:
        source = Path(source_path)
        extension = source.suffix.lower() or ".png"
        destination = app_data_dir() / "icons" / safe_icon_filename(entity_key, extension)
        shutil.copy2(source, destination)
        self.database.set_custom_icon(entity_key, str(destination))
        self.icon_ready.emit(entity_key)
        return str(destination)

    def _favicon_path(self, entity_key: str) -> Path:
        return app_data_dir() / "favicons" / safe_icon_filename(entity_key, ".png")

    def _request_favicon(self, entity_key: str, fallback_stage: int = 0) -> None:
        # Avoid duplicate network requests if several rows ask for the same icon.
        if any(meta[0] == entity_key for meta in self._pending.values()):
            return

        domain = entity_key.removeprefix("web:")
        if not domain:
            return

        if fallback_stage == 0:
            # Ask for a larger cached favicon first. Many sites publish only a
            # tiny favicon.ico, while this endpoint can return a sharper source.
            encoded = quote(f"https://{domain}", safe="")
            url = QUrl(
                f"https://www.google.com/s2/favicons?domain_url={encoded}&sz=128"
            )
        elif fallback_stage == 1:
            # Apple touch icons are commonly 120px or larger and are a useful
            # second chance when a high resolution favicon is not available.
            url = QUrl(f"https://{domain}/apple-touch-icon.png")
        else:
            # The traditional root favicon remains the final compatibility path.
            url = QUrl(f"https://{domain}/favicon.ico")

        request = QNetworkRequest(url)
        request.setRawHeader(b"User-Agent", b"Tracky/0.1")
        reply = self.network.get(request)
        self._pending[reply] = (entity_key, domain, fallback_stage)
        reply.finished.connect(lambda r=reply: self._favicon_finished(r))

    def _favicon_finished(self, reply: QNetworkReply) -> None:
        metadata = self._pending.pop(reply, None)
        if not metadata:
            reply.deleteLater()
            return

        entity_key, _domain, stage = metadata
        data = bytes(reply.readAll())
        pixmap = QPixmap()
        valid = bool(data) and pixmap.loadFromData(data)
        reply.deleteLater()

        if valid:
            path = self._favicon_path(entity_key)
            pixmap.save(str(path), "PNG")
            self.icon_ready.emit(entity_key)
        elif stage < 2:
            self._request_favicon(entity_key, fallback_stage=stage + 1)

    def _letter_icon(self, letter: str) -> QIcon:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor, QFont, QPainter

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#2B2140"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 64, 64, 14, 14)
        painter.setPen(QColor("#BDA7FF"))
        painter.setFont(QFont("Nunito", 24, QFont.Weight.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter or "?")
        painter.end()
        return QIcon(pixmap)
