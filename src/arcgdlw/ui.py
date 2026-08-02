import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import qdarktheme
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QCursor, QEnterEvent, QIcon, QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from arcgdlw import app_settings, supported_sites
from arcgdlw.models.downloader.downloader import Downloader
from arcgdlw.models.task.task import Task, TaskStatus
from arcgdlw.models.task.task_manager import TaskManager
from arcgdlw.paths import resource_path, subprocess_env

APP_ICON_PATH = resource_path("assets", "icon.png")

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

COLOR_ACCENT = "#0d6efd"
COLOR_ACCENT_HOVER = "#3b82f6"
COLOR_SUCCESS = "#198754"
COLOR_DANGER = "#dc3545"
COLOR_WARNING = "#f0ad4e"
COLOR_MUTED = "#6c757d"
COLOR_TEXT_MUTED = "#888888"
COLOR_BORDER = "rgba(255, 255, 255, 0.08)"

SIDEBAR_WIDTH = 188

# Extra QSS layered on top of qdarktheme for a more polished, minimal look.
# Button "variants" are selected via objectName so widgets can be built with
# the same QPushButton class but get distinct treatment (see _make_button).
_EXTRA_QSS = f"""
QPushButton {{
    border-radius: 6px;
    padding: 5px 14px;
    min-height: 28px;
}}
QPushButton#primaryButton {{
    background: {COLOR_ACCENT};
    border: 1px solid {COLOR_ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton#primaryButton:hover {{
    background: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#primaryButton:disabled {{
    background: rgba(13, 110, 253, 0.35);
    border-color: transparent;
    color: rgba(255, 255, 255, 0.6);
}}
QPushButton#dangerButton {{
    background: transparent;
    border: 1px solid rgba(220, 53, 69, 0.55);
    color: {COLOR_DANGER};
    font-weight: 600;
}}
QPushButton#dangerButton:hover {{
    background: rgba(220, 53, 69, 0.12);
}}
QPushButton#dangerButton:disabled {{
    border-color: rgba(220, 53, 69, 0.2);
    color: rgba(220, 53, 69, 0.35);
}}
QPushButton#ghostButton {{
    background: transparent;
    border: 1px solid rgba(255, 255, 255, 0.12);
}}
QPushButton#ghostButton:hover {{
    background: rgba(255, 255, 255, 0.06);
}}
QFrame#sidebar {{
    background: rgba(255, 255, 255, 0.02);
    border-right: 1px solid {COLOR_BORDER};
}}
QPushButton#navButton {{
    text-align: left;
    padding: 9px 20px;
    border: none;
    border-radius: 0px;
    border-left: 3px solid transparent;
    background: transparent;
    font-size: 13px;
    color: rgba(255, 255, 255, 0.68);
    min-height: 0;
}}
QPushButton#navButton:hover {{
    background: rgba(255, 255, 255, 0.05);
    color: white;
}}
QPushButton#navButton:checked {{
    background: rgba(13, 110, 253, 0.14);
    border-left: 3px solid {COLOR_ACCENT};
    color: white;
    font-weight: 600;
}}
QLineEdit, QComboBox {{
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
}}
QTextEdit {{
    border-radius: 6px;
}}
QScrollBar:vertical {{
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{ height: 0; }}
QProgressBar {{ border-radius: 4px; }}
QProgressBar::chunk {{ border-radius: 4px; }}
/* qdarktheme draws an accent underline under QCheckBox/QRadioButton on hover
   (QCheckBox:hover {{ border-bottom: 2px solid <accent> }}) — not wanted here. */
QCheckBox:hover, QRadioButton:hover {{
    border-bottom: 2px solid transparent;
}}
QTableWidget {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    gridline-color: rgba(255, 255, 255, 0.06);
}}
QTableWidget::item {{
    padding: 4px 6px;
}}
QTableWidget::item:selected {{
    background: rgba(13, 110, 253, 0.25);
}}
QHeaderView::section {{
    padding: 6px 8px;
    font-weight: 600;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
}}
"""

# Default gallery-dl config file locations (Linux order)
_DEFAULT_CONFIG_PATHS = [
    Path.home() / ".config" / "gallery-dl" / "config.json",
    Path.home() / ".gallery-dl.conf",
    Path("/etc/gallery-dl.conf"),
]


def _find_default_config() -> Path | None:
    for p in _DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Small style helpers — keep widget construction consistent across the app
# instead of repeating setStyleSheet/setCursor/setFixedHeight everywhere.
# ---------------------------------------------------------------------------


def _make_button(text: str, variant: str = "secondary", height: int = 32) -> QPushButton:
    """variant: 'primary' | 'danger' | 'ghost' | 'secondary' (default look)."""
    btn = QPushButton(text)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setFixedHeight(height)
    # Without this, QDialog auto-promotes the first eligible button to be the
    # implicit default (Enter-triggered) button. qdarktheme then styles it via
    # `QPushButton:default { color: <background color> }`, which — since our
    # ghost/secondary variants don't set an explicit text color — makes the
    # label render in the same color as the background (invisible). Buttons
    # that should be the real default call setDefault(True) explicitly, which
    # overrides this regardless.
    btn.setAutoDefault(False)
    if variant != "secondary":
        btn.setObjectName(f"{variant}Button")
    return btn


def _set_variant(btn: QPushButton, variant: str) -> None:
    btn.setObjectName(f"{variant}Button" if variant != "secondary" else "")
    style = btn.style()
    if style is not None:
        style.unpolish(btn)
        style.polish(btn)


def _h_divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {COLOR_BORDER}; max-height: 1px;")
    return line


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 20px; font-weight: 700;")
    return lbl


def _muted_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
    return lbl


def _eyebrow(text: str) -> QLabel:
    """Small accent-colored section header (e.g. inside a dialog)."""
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 10px; font-weight: 700;")
    return lbl


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
    return lbl


def _field(label_text: str, content: QWidget | QLayout) -> QVBoxLayout:
    """Label-above-widget block, used instead of QFormLayout's cramped label:field rows.

    Accepts a QLayout (e.g. an input + browse-button row) directly rather than
    forcing callers to wrap it in a plain QWidget first — QWidget.setLayout()
    applies non-zero default margins, which insets/misaligns the row against
    sibling fields added straight to the outer layout.
    """
    col = QVBoxLayout()
    col.setSpacing(5)
    col.addWidget(_field_label(label_text))
    if isinstance(content, QLayout):
        content.setContentsMargins(0, 0, 0, 0)
        col.addLayout(content)
    else:
        col.addWidget(content)
    return col


def _confirm(parent, title: str, text: str, confirm_label: str = "Yes", danger: bool = False) -> bool:
    """Styled replacement for QMessageBox.question with variant-matched buttons."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    cancel_btn = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
    confirm_btn = box.addButton(confirm_label, QMessageBox.ButtonRole.AcceptRole)
    _set_variant(cancel_btn, "ghost")
    _set_variant(confirm_btn, "danger" if danger else "primary")
    box.setDefaultButton(cancel_btn)
    box.exec()
    return box.clickedButton() is confirm_btn


def _format_age(seconds: float) -> str:
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours}h ago"
    days = int(hours // 24)
    return f"{days}d ago"


class SupportedSitesDialog(QDialog):
    """Browsable, filterable table of gallery-dl's supported sites, built live
    from https://codeberg.org/mikf/gallery-dl/raw/branch/master/docs/supportedsites.md
    (cached to disk so opening this dialog doesn't always hit the network)."""

    site_chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Supported Sites")
        self.resize(760, 560)
        self._sites: list[dict] = []
        self._worker: SupportedSitesWorker | None = None
        self._build_ui()
        self._load(force_refresh=False)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(_section_title("Supported Sites"))
        header.addStretch()
        self.refresh_btn = _make_button("Refresh", variant="ghost", height=28)
        self.refresh_btn.clicked.connect(lambda: self._load(force_refresh=True))
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        self.status_label = _muted_label("Loading…")
        layout.addWidget(self.status_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by site name or URL…")
        self.search_input.textChanged.connect(self._apply_filter)
        layout.addWidget(self.search_input)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Site", "URL", "Capabilities", "Auth"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        # Interactive (not ResizeToContents) for name/url/auth: with 386 rows a
        # single long outlier URL would otherwise blow that column's width out
        # and starve the "Capabilities" column, which needs the most room.
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(3, 90)
        self.table.doubleClicked.connect(self._use_selected)
        self.table.itemSelectionChanged.connect(
            lambda: self.use_btn.setEnabled(bool(self.table.selectedItems()))
        )
        layout.addWidget(self.table, stretch=1)

        layout.addWidget(_h_divider())

        btn_row = QHBoxLayout()
        btn_row.addWidget(_muted_label("Double-click a row (or select it) to use its URL."))
        btn_row.addStretch()
        close_btn = _make_button("Close", variant="ghost", height=32)
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)
        self.use_btn = _make_button("Use URL", variant="primary", height=32)
        self.use_btn.setEnabled(False)
        self.use_btn.clicked.connect(self._use_selected)
        btn_row.addWidget(self.use_btn)
        layout.addLayout(btn_row)

    def _load(self, force_refresh: bool):
        cached = supported_sites.get_cached_sites()
        if cached and not force_refresh:
            self._populate(cached)
            age = supported_sites.get_cache_age_seconds() or 0
            self.status_label.setText(f"{len(cached)} sites · cached {_format_age(age)}")

        self.refresh_btn.setEnabled(False)
        if not cached:
            self.status_label.setText("Loading supported sites…")
        self._worker = SupportedSitesWorker(force_refresh=force_refresh)
        self._worker.loaded.connect(self._on_loaded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_loaded(self, sites):
        self._populate(sites)
        self.status_label.setText(f"{len(sites)} sites · up to date")
        self.refresh_btn.setEnabled(True)

    def _on_failed(self, error: str):
        self.refresh_btn.setEnabled(True)
        if self._sites:
            self.status_label.setText(f"{len(self._sites)} sites · refresh failed ({error})")
        else:
            self.status_label.setText(f"Could not load supported sites: {error}")

    def _populate(self, sites: list[dict]):
        self._sites = sites
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(sites))
        for row, site in enumerate(sites):
            name_item = QTableWidgetItem(site["name"])
            url_item = QTableWidgetItem(site["url"])
            cap_item = QTableWidgetItem(site["capabilities"])
            cap_item.setToolTip(site["capabilities"])
            auth_item = QTableWidgetItem(site["auth"])
            for item in (name_item, url_item, cap_item, auth_item):
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, url_item)
            self.table.setItem(row, 2, cap_item)
            self.table.setItem(row, 3, auth_item)
        self.table.setSortingEnabled(True)
        self._apply_filter(self.search_input.text())

    def _apply_filter(self, text: str):
        text = text.strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            name = self.table.item(row, 0).text().lower()
            url = self.table.item(row, 1).text().lower()
            self.table.setRowHidden(row, text not in name and text not in url)

    def _use_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        url_item = self.table.item(row, 1)
        if url_item:
            self.site_chosen.emit(url_item.text())
            self.accept()


# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------


class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, output_folder, urls, target_format, override_format, archive_format):
        super().__init__()
        self.output_folder = output_folder
        self.urls = urls
        self.target_format = target_format
        self.override_format = override_format
        self.archive_format = archive_format

    def run(self):
        try:
            downloader = Downloader(
                outputFolder=self.output_folder,
                urls=self.urls,
                targetFormat=self.target_format,
                overrideFormat=self.override_format,
                archiveFormat=self.archive_format,
                configFile=app_settings.get("gallery_dl_config"),
            )
            downloader.download(log_callback=self.log_signal.emit)
            self.log_signal.emit("\n✅ All downloads complete!")
        except Exception as e:
            self.log_signal.emit(f"\n❌ Fatal Error: {str(e)}")
        finally:
            self.finished_signal.emit()


class TaskWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)   # current_url_index, total_urls
    finished_signal = pyqtSignal(bool, bool, str)  # success, cancelled, error_message

    def __init__(self, task: Task):
        super().__init__()
        self.task = task
        self.cancel_event = threading.Event()

    def request_cancel(self):
        self.cancel_event.set()

    def run(self):
        try:
            downloader = Downloader(
                outputFolder=self.task.output_folder,
                urls=self.task.urls,
                targetFormat=self.task.target_format,
                overrideFormat=self.task.override_format,
                archiveFormat=self.task.archive_format,
                configFile=app_settings.get("gallery_dl_config"),
                cookiesFile=self.task.cookies_file or None,
                createSubfolder=self.task.create_subfolder,
            )
            _files, cancelled = downloader.download(
                log_callback=self.log_signal.emit,
                progress_callback=lambda cur, tot: self.progress_signal.emit(cur, tot),
                cancel_event=self.cancel_event,
            )
            self.finished_signal.emit(not cancelled, cancelled, "")
        except Exception as e:
            self.finished_signal.emit(False, self.cancel_event.is_set(), str(e))


class PreviewWorker(QThread):
    preview_ready = pyqtSignal(str, str)  # task_id, image_path

    def __init__(self, task: Task, manager: TaskManager):
        super().__init__()
        self.task = task
        self.manager = manager

    def run(self):
        preview_path = self.manager.fetch_preview(self.task)
        if preview_path:
            self.task.preview_image = preview_path
            self.manager.update(self.task)
            self.preview_ready.emit(self.task.id, str(preview_path))


class SupportedSitesWorker(QThread):
    """Fetches/parses gallery-dl's supported-sites table off the GUI thread."""

    loaded = pyqtSignal(object)  # list[dict]
    failed = pyqtSignal(str)

    def __init__(self, force_refresh: bool = False):
        super().__init__()
        self.force_refresh = force_refresh

    def run(self):
        try:
            sites = supported_sites.get_sites(force_refresh=self.force_refresh)
            self.loaded.emit(sites)
        except Exception as e:
            self.failed.emit(str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_folder_native(start_path: str) -> str | None:
    for cmd in (
        ["kdialog", "--getexistingdirectory", start_path],
        ["zenity", "--file-selection", "--directory", f"--filename={start_path}/"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=subprocess_env())
            return result.stdout.strip() or None
        except FileNotFoundError:
            continue
    return None


def _pick_file_native(start_path: str, title: str = "Select File", filter: str = "*.json *.conf") -> str | None:
    for cmd in (
        ["kdialog", "--getopenfilename", start_path, filter],
        ["zenity", "--file-selection", f"--filename={start_path}/", "--title", title],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=subprocess_env())
            return result.stdout.strip() or None
        except FileNotFoundError:
            continue
    return None


def _open_folder(path: str) -> None:
    """Open `path` in the system's default file manager."""
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
        return
    for cmd in (["xdg-open", path], ["dolphin", path], ["nautilus", path]):
        try:
            subprocess.Popen(cmd, env=subprocess_env())
            return
        except FileNotFoundError:
            continue


# ---------------------------------------------------------------------------
# Preview label with hover popup
# ---------------------------------------------------------------------------


class PreviewLabel(QLabel):
    """Thumbnail that pops up a full-size image preview on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._popup: QWidget | None = None
        self._image_path: str | None = None

    def set_image_path(self, path: str | None):
        self._image_path = path

    def enterEvent(self, event: QEnterEvent | None) -> None:
        if self._image_path:
            self._show_popup()
        super().enterEvent(event)

    def leaveEvent(self, a0: QEvent | None) -> None:
        self._hide_popup()
        super().leaveEvent(a0)

    def _show_popup(self):
        if self._popup or not self._image_path:
            return
        pixmap = QPixmap(self._image_path)
        if pixmap.isNull():
            return

        screen = QApplication.screenAt(QCursor.pos())
        screen_rect = screen.availableGeometry() if screen else None
        max_dim = 700
        if screen_rect is not None:
            max_dim = min(max_dim, screen_rect.width() * 2 // 3, screen_rect.height() * 2 // 3)

        scaled = pixmap.scaled(
            max_dim, max_dim,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        popup = QWidget(self, Qt.WindowType.ToolTip)
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        popup.setStyleSheet(
            "background: #1a1a1a; border: 1px solid #444; border-radius: 6px; padding: 4px;"
        )
        lyt = QVBoxLayout(popup)
        lyt.setContentsMargins(4, 4, 4, 4)
        img_lbl = QLabel()
        img_lbl.setPixmap(scaled)
        lyt.addWidget(img_lbl)
        popup.adjustSize()

        cx, cy = QCursor.pos().x(), QCursor.pos().y()
        px, py = cx + 18, cy - popup.height() // 2
        if screen_rect is not None:
            if px + popup.width() > screen_rect.right():
                px = cx - popup.width() - 18
            py = max(screen_rect.top(), min(py, screen_rect.bottom() - popup.height()))

        popup.move(px, py)
        popup.show()
        self._popup = popup

    def _hide_popup(self):
        if self._popup:
            self._popup.close()
            self._popup.deleteLater()
            self._popup = None


# ---------------------------------------------------------------------------
# Task UI components
# ---------------------------------------------------------------------------


_STATUS_COLORS = {
    TaskStatus.PENDING: COLOR_MUTED,
    TaskStatus.RUNNING: COLOR_ACCENT,
    TaskStatus.COMPLETED: COLOR_SUCCESS,
    TaskStatus.ERROR: COLOR_DANGER,
    TaskStatus.CANCELLED: COLOR_WARNING,
}


class TaskCard(QFrame):
    run_requested = pyqtSignal(str)
    cancel_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    clone_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("taskCard")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet("""
            QFrame#taskCard {
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.025);
            }
            QFrame#taskCard:hover {
                border: 1px solid rgba(255, 255, 255, 0.18);
                background: rgba(255, 255, 255, 0.04);
            }
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        # --- Top row: thumbnail | info | status ---
        top = QHBoxLayout()
        top.setSpacing(14)

        self.preview_label = PreviewLabel()
        self.preview_label.setMinimumSize(80, 80)
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setText("?")
        self.preview_label.setStyleSheet(
            "border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; "
            "background: rgba(255,255,255,0.05); font-size: 24px; color: #666;"
        )
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        top.addWidget(self.preview_label)

        info_col = QVBoxLayout()
        info_col.setSpacing(5)

        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_col.addWidget(self.name_label)

        self.details_label = _muted_label("")
        info_col.addWidget(self.details_label)

        self.error_label = QLabel()
        self.error_label.setStyleSheet(f"color: {COLOR_DANGER}; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        info_col.addWidget(self.error_label)

        info_col.addStretch()
        top.addLayout(info_col, 1)

        self.status_label = QLabel()
        self.status_label.setFixedWidth(92)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(
            "border-radius: 10px; padding: 3px 8px; font-size: 11px; font-weight: bold;"
        )
        top.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignTop)

        outer.addLayout(top)

        # --- Progress bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        outer.addWidget(self.progress_bar)

        # --- Divider ---
        outer.addWidget(_h_divider())

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.run_cancel_btn = _make_button("▶ Run", variant="primary", height=30)
        self.run_cancel_btn.clicked.connect(self._on_run_cancel_clicked)
        btn_row.addWidget(self.run_cancel_btn)

        self.edit_btn = _make_button("Edit", variant="secondary", height=30)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.task.id))
        btn_row.addWidget(self.edit_btn)

        self.clone_btn = _make_button("Clone", variant="secondary", height=30)
        self.clone_btn.clicked.connect(lambda: self.clone_requested.emit(self.task.id))
        btn_row.addWidget(self.clone_btn)

        self.delete_btn = _make_button("Delete", variant="danger", height=30)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.task.id))
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.open_folder_btn = _make_button("Open Folder", variant="ghost", height=30)
        self.open_folder_btn.clicked.connect(lambda: _open_folder(self.task.output_folder))
        self.open_folder_btn.hide()
        btn_row.addWidget(self.open_folder_btn)

        self.log_toggle_btn = _make_button("Logs", variant="ghost", height=30)
        self.log_toggle_btn.setCheckable(True)
        self.log_toggle_btn.toggled.connect(self._on_log_toggle)
        btn_row.addWidget(self.log_toggle_btn)

        outer.addLayout(btn_row)

        # --- Log area ---
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(
            "font-family: monospace; font-size: 12px; "
            "background: rgba(0,0,0,0.25); border-radius: 6px;"
        )
        self.log_area.setMinimumHeight(110)
        self.log_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.log_area.hide()
        outer.addWidget(self.log_area)

    def _on_run_cancel_clicked(self):
        if self.task.status == TaskStatus.RUNNING:
            self.cancel_requested.emit(self.task.id)
        else:
            self.run_requested.emit(self.task.id)

    def _on_log_toggle(self, checked: bool):
        self.log_area.setVisible(checked)
        self.log_toggle_btn.setText("Hide Logs" if checked else "Logs")

    def _refresh(self):
        task = self.task
        self.name_label.setText(task.name)

        count = len(task.urls)
        archive_str = task.archive_format or "no archive"
        self.details_label.setText(
            f"{count} URL{'s' if count != 1 else ''} · {task.target_format} · {archive_str}"
        )

        color = _STATUS_COLORS.get(task.status, COLOR_MUTED)
        self.status_label.setText(task.status.value)
        self.status_label.setStyleSheet(
            f"border-radius: 10px; padding: 3px 8px; font-size: 11px; "
            f"font-weight: bold; background: {color}22; color: {color}; "
            f"border: 1px solid {color}55;"
        )

        if task.status == TaskStatus.ERROR and task.error_message:
            self.error_label.setText(task.error_message)
            self.error_label.show()
        else:
            self.error_label.hide()

        self._refresh_preview()

        running = task.status == TaskStatus.RUNNING
        if running:
            self.run_cancel_btn.setText("■ Cancel")
            _set_variant(self.run_cancel_btn, "danger")
        else:
            self.run_cancel_btn.setText("▶ Run")
            _set_variant(self.run_cancel_btn, "primary")
        self.edit_btn.setEnabled(not running)
        self.delete_btn.setEnabled(not running)
        self.open_folder_btn.setVisible(task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED))

    def resizeEvent(self, a0: QResizeEvent | None) -> None:
        super().resizeEvent(a0)
        # Scale preview between 80 and 160 px based on card width
        size = max(80, min(160, self.width() // 6))
        if self.preview_label.width() != size:
            self.preview_label.setFixedSize(size, size)
            self._refresh_preview()

    def _refresh_preview(self):
        task = self.task
        size = self.preview_label.width() or 80
        img_path = None
        if task.preview_image and task.preview_image.exists():
            pixmap = QPixmap(str(task.preview_image))
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.preview_label.setPixmap(scaled)
                self.preview_label.setText("")
                img_path = str(task.preview_image)
        if img_path is None:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("?")
        self.preview_label.set_image_path(img_path)

    def update_task(self, task: Task):
        self.task = task
        self._refresh()

    def set_running(self, is_running: bool):
        self.progress_bar.setVisible(is_running)
        if is_running:
            self.progress_bar.setMaximum(0)
            self.progress_bar.setValue(0)

    def update_progress(self, current: int, total: int):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
        else:
            self.progress_bar.setMaximum(0)

    def append_log(self, text: str):
        self.log_area.append(text)
        sb = self.log_area.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())
        if not self.log_toggle_btn.isChecked():
            self.log_toggle_btn.setChecked(True)


class CreateTaskDialog(QDialog):
    def __init__(self, parent=None, task: Task | None = None):
        super().__init__(parent)
        self._existing = task
        self.setWindowTitle("Edit Task" if task else "Create Task")
        self.setMinimumWidth(580)
        self._build_ui()
        if task:
            self._populate(task)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(8)

        layout.addWidget(_section_title("Edit Task" if self._existing else "Create Task"))
        layout.addSpacing(4)
        layout.addWidget(_h_divider())
        layout.addSpacing(2)

        # --- General ---
        layout.addWidget(_eyebrow("General"))

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My task name")
        layout.addLayout(_field("Name", self.name_input))

        urls_header = QHBoxLayout()
        urls_header.addWidget(_field_label("Gallery URLs"))
        urls_header.addStretch()
        sites_btn = _make_button("Show Supported Sites", variant="ghost", height=22)
        sites_btn.clicked.connect(self._show_supported_sites)
        urls_header.addWidget(sites_btn)

        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText(
            "https://gallery-url-1.com/...\nhttps://gallery-url-2.com/...\n(One URL per line)"
        )
        self.urls_input.setFixedHeight(56)

        urls_col = QVBoxLayout()
        urls_col.setSpacing(5)
        urls_col.addLayout(urls_header)
        urls_col.addWidget(self.urls_input)
        layout.addLayout(urls_col)

        # --- Output & format ---
        layout.addSpacing(6)
        layout.addWidget(_eyebrow("Output & Format"))

        folder_row = QHBoxLayout()
        self.output_input = QLineEdit(str(Path("./downloads").resolve()))
        self.output_input.setReadOnly(True)
        self.output_input.setFixedHeight(28)
        browse_btn = _make_button("Browse", variant="secondary", height=28)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.output_input)
        folder_row.addWidget(browse_btn)
        layout.addLayout(_field("Output Folder", folder_row))

        self.subfolder_checkbox = QCheckBox("Create a sub-folder")
        self.subfolder_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subfolder_checkbox.setToolTip(
            "Keep each URL's downloads in its own sub-folder (named automatically\n"
            "by gallery-dl) instead of dumping every file into the output folder."
        )
        layout.addWidget(self.subfolder_checkbox)

        format_section = QHBoxLayout()
        format_section.setSpacing(20)

        self.target_format_combo = QComboBox()
        self.target_format_combo.addItems(["gif", "mp4", "webm", "mkv"])
        self.override_checkbox = QCheckBox("Force conversion")
        self.override_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.override_checkbox.setToolTip(
            "Force conversion even if duration/audio rules are not met."
        )
        target_row = QHBoxLayout()
        target_row.addWidget(self.target_format_combo)
        target_row.addWidget(self.override_checkbox)
        target_row.addStretch()
        format_section.addLayout(_field("Target Format", target_row), 2)

        self.archive_combo = QComboBox()
        self.archive_combo.addItems(["None", "zip", "cbz", "rar", "cbr"])
        format_section.addLayout(_field("Archive Mode", self.archive_combo), 1)

        layout.addLayout(format_section)

        # --- Advanced ---
        layout.addSpacing(6)
        layout.addWidget(_eyebrow("Advanced"))

        cookies_row = QHBoxLayout()
        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("Optional — path to cookies.txt")
        self.cookies_input.setReadOnly(True)
        self.cookies_input.setFixedHeight(28)
        cookies_browse_btn = _make_button("Browse", variant="secondary", height=28)
        cookies_browse_btn.clicked.connect(self._browse_cookies)
        cookies_clear_btn = _make_button("Clear", variant="ghost", height=28)
        cookies_clear_btn.clicked.connect(lambda: self.cookies_input.clear())
        cookies_row.addWidget(self.cookies_input)
        cookies_row.addWidget(cookies_browse_btn)
        cookies_row.addWidget(cookies_clear_btn)
        layout.addLayout(_field("Cookies File", cookies_row))

        self.auto_start_check = QCheckBox("Start automatically after creation")
        self.auto_start_check.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.auto_start_check)

        layout.addSpacing(4)
        layout.addWidget(_h_divider())

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = _make_button("Cancel", variant="ghost", height=32)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.ok_btn = _make_button("Save" if self._existing else "Create", variant="primary", height=32)
        self.ok_btn.setDefault(True)
        self.ok_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

    def _browse_folder(self):
        folder = _pick_folder_native(self.output_input.text())
        if folder:
            self.output_input.setText(folder)

    def _browse_cookies(self):
        start = str(Path.home())
        chosen = _pick_file_native(start, "Select cookies.txt", filter="*.txt")
        if chosen:
            self.cookies_input.setText(chosen)

    def _populate(self, task: Task):
        self.name_input.setText(task.name)
        self.urls_input.setPlainText("\n".join(task.urls))
        self.output_input.setText(task.output_folder)
        self.subfolder_checkbox.setChecked(task.create_subfolder)
        idx = self.target_format_combo.findText(task.target_format)
        if idx >= 0:
            self.target_format_combo.setCurrentIndex(idx)
        self.override_checkbox.setChecked(task.override_format)
        combo_val = task.archive_format or "None"
        idx = self.archive_combo.findText(combo_val)
        if idx >= 0:
            self.archive_combo.setCurrentIndex(idx)
        self.cookies_input.setText(task.cookies_file or "")
        self.auto_start_check.setChecked(task.start_automatically)

    def _show_supported_sites(self):
        dlg = SupportedSitesDialog(self)
        dlg.site_chosen.connect(self._insert_url)
        dlg.exec()

    def _insert_url(self, url: str):
        current = self.urls_input.toPlainText().rstrip("\n")
        self.urls_input.setPlainText(f"{current}\n{url}" if current else url)
        cursor = self.urls_input.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.urls_input.setTextCursor(cursor)

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        urls = [u.strip() for u in self.urls_input.toPlainText().splitlines() if u.strip()]
        ok = True
        if not name:
            self.name_input.setStyleSheet(f"border: 1px solid {COLOR_DANGER};")
            ok = False
        else:
            self.name_input.setStyleSheet("")

        malformed = [u for u in urls if not supported_sites.is_well_formed_url(u)]
        if not urls or malformed:
            self.urls_input.setStyleSheet(f"border: 1px solid {COLOR_DANGER};")
            ok = False
            if malformed:
                QMessageBox.warning(
                    self, "Invalid URLs",
                    "These lines don't look like valid URLs (need http:// or https://):\n\n"
                    + "\n".join(malformed),
                )
        else:
            self.urls_input.setStyleSheet("")

        if not ok:
            return

        cached_sites = supported_sites.get_cached_sites()
        if cached_sites:
            known_hosts = supported_sites.extract_hostnames(cached_sites)
            unknown = supported_sites.unrecognized_urls(urls, known_hosts)
            if unknown:
                proceed = _confirm(
                    self, "Unrecognized Sites",
                    "These URLs don't match any site in gallery-dl's supported sites "
                    "list. They might still work (gallery-dl also supports generic/"
                    "direct-link downloads), but double-check them:\n\n"
                    + "\n".join(unknown),
                    confirm_label="Use anyway",
                )
                if not proceed:
                    return

        self.accept()

    def get_data(self) -> dict:
        archive_text = self.archive_combo.currentText()
        cookies = self.cookies_input.text().strip()
        return {
            "name": self.name_input.text().strip(),
            "urls": [u.strip() for u in self.urls_input.toPlainText().splitlines() if u.strip()],
            "output_folder": self.output_input.text(),
            "target_format": self.target_format_combo.currentText(),
            "override_format": self.override_checkbox.isChecked(),
            "archive_format": archive_text if archive_text != "None" else None,
            "cookies_file": cookies if cookies else None,
            "create_subfolder": self.subfolder_checkbox.isChecked(),
            "start_automatically": self.auto_start_check.isChecked(),
        }


class TasksTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._manager = TaskManager()
        self._workers: dict[str, TaskWorker] = {}
        self._preview_workers: dict[str, PreviewWorker] = {}
        self._cards: dict[str, TaskCard] = {}
        self._build_ui()
        self._load_tasks()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(_section_title("Tasks"))
        header.addStretch()
        create_btn = _make_button("+ Create Task", variant="primary", height=34)
        create_btn.clicked.connect(self._open_create_dialog)
        header.addWidget(create_btn)
        layout.addLayout(header)

        layout.addWidget(_h_divider())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(10)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._empty_label = QLabel("No tasks yet — create one to get started.")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 13px; padding: 60px 0;")
        self._cards_layout.addWidget(self._empty_label)

        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_widget)
        layout.addWidget(scroll)

    def _load_tasks(self):
        for task in self._manager.tasks:
            self._insert_card(task)
        self._update_empty_state()

    def _insert_card(self, task: Task):
        card = TaskCard(task)
        card.run_requested.connect(self._run_task)
        card.cancel_requested.connect(self._cancel_task)
        card.edit_requested.connect(self._edit_task)
        card.clone_requested.connect(self._clone_task)
        card.delete_requested.connect(self._delete_task)
        self._cards[task.id] = card
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)
        self._update_empty_state()

    def _update_empty_state(self):
        self._empty_label.setVisible(len(self._cards) == 0)

    def _open_create_dialog(self):
        dlg = CreateTaskDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        task = Task(**data)
        self._manager.create(task)
        self._insert_card(task)
        self._start_preview_fetch(task)
        if task.start_automatically:
            self._run_task(task.id)

    def _start_preview_fetch(self, task: Task):
        worker = PreviewWorker(task, self._manager)
        worker.preview_ready.connect(self._on_preview_ready)
        self._preview_workers[task.id] = worker
        worker.start()

    def _on_preview_ready(self, task_id: str, _path: str):
        task = self._manager.get(task_id)
        card = self._cards.get(task_id)
        if task and card:
            card.update_task(task)
        self._preview_workers.pop(task_id, None)

    def _run_task(self, task_id: str):
        if task_id in self._workers:
            return
        task = self._manager.get(task_id)
        if not task:
            return
        task.status = TaskStatus.RUNNING
        task.error_message = None
        self._manager.update(task)
        card = self._cards.get(task_id)
        if card:
            card.update_task(task)
            card.set_running(True)
            card.append_log(f"⏳ Starting task: {task.name}")
        worker = TaskWorker(task)
        worker.log_signal.connect(lambda msg, tid=task_id: self._on_log(tid, msg))
        worker.progress_signal.connect(
            lambda cur, tot, tid=task_id: self._on_progress(tid, cur, tot)
        )
        worker.finished_signal.connect(
            lambda ok, cancelled, err, tid=task_id: self._on_finished(tid, ok, cancelled, err)
        )
        self._workers[task_id] = worker
        worker.start()

    def _cancel_task(self, task_id: str):
        worker = self._workers.get(task_id)
        if not worker:
            return
        worker.request_cancel()
        card = self._cards.get(task_id)
        if card:
            card.append_log("\n🛑 Cancelling…")

    def _on_log(self, task_id: str, msg: str):
        card = self._cards.get(task_id)
        if card:
            card.append_log(msg)

    def _on_progress(self, task_id: str, current: int, total: int):
        card = self._cards.get(task_id)
        if card:
            card.update_progress(current, total)

    def _on_finished(self, task_id: str, success: bool, cancelled: bool, error_msg: str):
        task = self._manager.get(task_id)
        card = self._cards.get(task_id)
        if task:
            if cancelled:
                task.status = TaskStatus.CANCELLED
                task.error_message = None
            else:
                task.status = TaskStatus.COMPLETED if success else TaskStatus.ERROR
                task.error_message = error_msg if not success else None
            self._manager.update(task)
        if card:
            card.set_running(False)
            if task:
                card.update_task(task)
            if cancelled:
                card.append_log("\n🛑 Task cancelled — files already downloaded were kept.")
            elif success:
                card.append_log("\n✅ Task completed!")
            else:
                card.append_log(f"\n❌ Task failed: {error_msg}")
        self._workers.pop(task_id, None)

    def _edit_task(self, task_id: str):
        task = self._manager.get(task_id)
        if not task:
            return
        dlg = CreateTaskDialog(self, task=task)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_data()
        urls_changed = data["urls"] != task.urls
        task.name = data["name"]
        task.urls = data["urls"]
        task.output_folder = data["output_folder"]
        task.target_format = data["target_format"]
        task.override_format = data["override_format"]
        task.archive_format = data["archive_format"]
        task.cookies_file = data["cookies_file"]
        task.create_subfolder = data["create_subfolder"]
        task.start_automatically = data["start_automatically"]
        if task.status in (TaskStatus.ERROR, TaskStatus.CANCELLED):
            task.status = TaskStatus.PENDING
            task.error_message = None
        self._manager.update(task)
        card = self._cards.get(task_id)
        if card:
            card.update_task(task)
        if urls_changed:
            task.preview_image = None
            self._manager.update(task)
            self._start_preview_fetch(task)

    def _clone_task(self, task_id: str):
        task = self._manager.get(task_id)
        if not task:
            return
        cloned = self._manager.clone(task)
        self._insert_card(cloned)

    def _delete_task(self, task_id: str):
        task = self._manager.get(task_id)
        if not task:
            return
        confirmed = _confirm(
            self, "Delete Task", f'Delete "{task.name}"? This cannot be undone.',
            confirm_label="Delete", danger=True,
        )
        if not confirmed:
            return
        card = self._cards.pop(task_id, None)
        if card:
            card.setParent(None)
            card.deleteLater()
        self._manager.delete(task_id)
        self._update_empty_state()


# ---------------------------------------------------------------------------
# Download tab
# ---------------------------------------------------------------------------


class DownloadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(_section_title("Gallery Downloader"))
        layout.addWidget(_muted_label("One-off download — not saved as a task."))

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText(
            "https://gallery-url-1.com/...\nhttps://gallery-url-2.com/...\n(One URL per line)"
        )
        self.urls_input.setFixedHeight(80)
        form.addRow("Gallery URLs:", self.urls_input)

        folder_row = QHBoxLayout()
        self.output_input = QLineEdit(str(Path("./downloads").resolve()))
        self.output_input.setReadOnly(True)
        browse_btn = _make_button("Browse", variant="secondary", height=28)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.output_input)
        folder_row.addWidget(browse_btn)
        form.addRow("Output Folder:", folder_row)

        format_row = QHBoxLayout()
        self.target_format_combo = QComboBox()
        self.target_format_combo.addItems(["gif", "mp4", "webm", "mkv"])
        self.override_checkbox = QCheckBox("Force conversion (Override)")
        self.override_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.override_checkbox.setToolTip(
            "Force conversion even if duration/audio rules are not met."
        )
        format_row.addWidget(self.target_format_combo)
        format_row.addWidget(self.override_checkbox)
        format_row.addStretch()
        form.addRow("Target Format:", format_row)

        self.archive_combo = QComboBox()
        self.archive_combo.addItems(["None", "zip", "cbz", "rar", "cbr"])
        self.archive_combo.setFixedWidth(150)
        form.addRow("Archive Mode:", self.archive_combo)

        layout.addLayout(form)
        layout.addWidget(_h_divider())

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(
            "font-family: monospace; font-size: 13px; "
            "background: rgba(0,0,0,0.2); border-radius: 6px;"
        )
        self.log_area.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.log_area, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self.start_btn = _make_button("Start Download", variant="primary", height=42)
        self.start_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self.start_btn, 1)

        self.open_folder_btn = _make_button("Open Folder", variant="ghost", height=42)
        self.open_folder_btn.clicked.connect(
            lambda: _open_folder(self.output_input.text())
        )
        self.open_folder_btn.hide()
        btn_row.addWidget(self.open_folder_btn)

        layout.addLayout(btn_row)

    def _browse_folder(self):
        folder = _pick_folder_native(self.output_input.text())
        if folder:
            self.output_input.setText(folder)

    def _append_log(self, text: str):
        self.log_area.append(text)
        sb = self.log_area.verticalScrollBar()
        if sb is not None:
            sb.setValue(sb.maximum())

    def _start_download(self):
        urls = [u.strip() for u in self.urls_input.toPlainText().splitlines() if u.strip()]
        if not urls:
            self._append_log("⚠️ Error: Please enter at least one valid URL.")
            return
        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")
        self.open_folder_btn.hide()
        archive_text = self.archive_combo.currentText()
        self._append_log(f"⏳ Starting download for {len(urls)} URL(s)...")
        self._worker = DownloadWorker(
            output_folder=self.output_input.text(),
            urls=urls,
            target_format=self.target_format_combo.currentText(),
            override_format=self.override_checkbox.isChecked(),
            archive_format=archive_text if archive_text != "None" else None,
        )
        self._worker.log_signal.connect(self._append_log)
        self._worker.finished_signal.connect(self._download_finished)
        self._worker.start()

    def _download_finished(self):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Download")
        self.open_folder_btn.show()


# ---------------------------------------------------------------------------
# Config tab
# ---------------------------------------------------------------------------


class ConfigTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(_section_title("gallery-dl Configuration"))
        layout.addWidget(_muted_label(
            "Edit the gallery-dl config file. Changes apply to all downloads and tasks."
        ))

        layout.addWidget(_h_divider())

        # --- File path row ---
        path_form = QFormLayout()
        path_form.setSpacing(10)
        path_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("No config file selected")
        self.path_input.setReadOnly(True)
        path_row.addWidget(self.path_input)

        browse_btn = _make_button("Browse…", variant="secondary", height=30)
        browse_btn.clicked.connect(self._browse_config)
        path_row.addWidget(browse_btn)

        path_form.addRow("Config file:", path_row)
        layout.addLayout(path_form)

        # --- Status + quick actions ---
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 12px;")
        actions_row.addWidget(self.status_label)
        actions_row.addStretch()

        self.create_btn = _make_button("Create Default Config", variant="secondary", height=30)
        self.create_btn.setToolTip(
            "Runs: gallery-dl --config-create\n"
            "Creates a default config at ~/.config/gallery-dl/config.json"
        )
        self.create_btn.clicked.connect(self._create_default_config)
        actions_row.addWidget(self.create_btn)

        self.open_folder_btn = _make_button("Open Folder", variant="ghost", height=30)
        self.open_folder_btn.clicked.connect(self._open_folder)
        actions_row.addWidget(self.open_folder_btn)

        layout.addLayout(actions_row)
        layout.addWidget(_h_divider())

        # --- JSON editor ---
        layout.addWidget(_muted_label("Config content (JSON):"))

        self.editor = QTextEdit()
        self.editor.setStyleSheet(
            "font-family: monospace; font-size: 13px; "
            "background: rgba(0,0,0,0.2); border-radius: 6px;"
        )
        self.editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self.editor, stretch=1)

        # --- Bottom buttons ---
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()

        reload_btn = _make_button("Reload", variant="ghost", height=32)
        reload_btn.clicked.connect(self._load_config)
        bottom_row.addWidget(reload_btn)

        save_btn = _make_button("Save", variant="primary", height=32)
        save_btn.clicked.connect(self._save_config)
        bottom_row.addWidget(save_btn)

        layout.addLayout(bottom_row)

    def _resolve_config_path(self) -> Path | None:
        """Return the active config path: custom from app_settings, or auto-detected default."""
        custom = app_settings.get("gallery_dl_config")
        if custom:
            return Path(custom)
        return _find_default_config()

    def _load_config(self):
        config_path = self._resolve_config_path()
        if config_path and config_path.exists():
            self.path_input.setText(str(config_path))
            self.status_label.setText(f"✔ Found: {config_path}")
            self.status_label.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS};")
            try:
                self.editor.setPlainText(config_path.read_text())
            except Exception as e:
                self.editor.setPlainText(f"# Could not read file: {e}")
        else:
            self.path_input.setText("")
            self.status_label.setText("✘ No config file found")
            self.status_label.setStyleSheet(f"font-size: 12px; color: {COLOR_DANGER};")
            self.editor.setPlainText(
                '{\n  "extractor": {},\n  "downloader": {},\n  "output": {}\n}\n'
            )
        self.open_folder_btn.setEnabled(bool(config_path))

    def _browse_config(self):
        start = str(Path.home() / ".config" / "gallery-dl")
        chosen = _pick_file_native(start, "Select gallery-dl config file")
        if not chosen:
            return
        app_settings.set_value("gallery_dl_config", chosen)
        self._load_config()

    def _create_default_config(self):
        try:
            result = subprocess.run(
                ["gallery-dl", "--config-create"],
                capture_output=True, text=True, timeout=15,
                env=subprocess_env(),
            )
            # gallery-dl --config-create exits 0 on success, may print the path
            created = _find_default_config()
            if created:
                # Clear custom override so the default is picked up
                app_settings.set_value("gallery_dl_config", None)
                self._load_config()
                QMessageBox.information(
                    self, "Config Created", f"Default config created at:\n{created}"
                )
            else:
                QMessageBox.warning(
                    self, "Config Create", result.stdout or result.stderr or "Unknown result."
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _open_folder(self):
        config_path = self._resolve_config_path()
        if not config_path:
            return
        _open_folder(str(config_path.parent))

    def _save_config(self):
        config_path = self._resolve_config_path()
        if not config_path:
            QMessageBox.warning(
                self, "No Config File",
                "No config file path is set. Browse to an existing file or create a default one first.",
            )
            return

        content = self.editor.toPlainText()
        try:
            json.loads(content)  # validate JSON before saving
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Invalid JSON", f"Cannot save — invalid JSON:\n{e}")
            return

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(content)
            self.status_label.setText(f"✔ Saved: {config_path}")
            self.status_label.setStyleSheet(f"font-size: 12px; color: {COLOR_SUCCESS};")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARCGDLW")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(920, 640)
        self.setMinimumSize(760, 520)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.addWidget(TasksTab())
        self.stack.addWidget(DownloadTab())
        self.stack.addWidget(ConfigTab())

        root.addWidget(self._build_sidebar())
        root.addWidget(self.stack, 1)

        # Warm the supported-sites cache in the background (held by this
        # long-lived window, not a dialog) so task creation's URL check has
        # data available without ever blocking on the network.
        self._sites_prefetch = SupportedSitesWorker(force_refresh=False)
        self._sites_prefetch.start()

    def _build_sidebar(self) -> QWidget:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(2)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 22, 16, 22)
        header_layout.setSpacing(10)

        icon_lbl = QLabel()
        icon_pixmap = QPixmap(str(APP_ICON_PATH))
        if not icon_pixmap.isNull():
            icon_lbl.setPixmap(
                icon_pixmap.scaled(
                    24, 24,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        header_layout.addWidget(icon_lbl)

        title_lbl = QLabel("ARCGDLW")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 700;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addWidget(header)

        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for label, index in (("Tasks", 0), ("Download", 1), ("Config", 2)):
            btn = QPushButton(label)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(38)
            btn.clicked.connect(lambda _checked, i=index: self.stack.setCurrentIndex(i))
            self._nav_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch()

        first_btn = self._nav_group.buttons()[0]
        first_btn.setChecked(True)

        return sidebar


def launch_gui():
    import sys

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    # Pinned to "dark": every custom color in _EXTRA_QSS (sidebar, card borders,
    # log backgrounds, nav text) is a light-on-dark overlay. "auto" would follow
    # a light OS theme and make that text unreadable (e.g. white nav labels on
    # a light sidebar background).
    qdarktheme.setup_theme("dark", additional_qss=_EXTRA_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
