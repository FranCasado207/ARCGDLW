import json
import subprocess
from pathlib import Path

import qdarktheme
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QCursor, QEnterEvent, QIcon, QPixmap, QResizeEvent
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import app_settings
from models.downloader.downloader import Downloader
from models.task.task import Task, TaskStatus
from models.task.task_manager import TaskManager
from paths import resource_path, subprocess_env

APP_ICON_PATH = resource_path("assets", "icon.png")

# Extra QSS layered on top of qdarktheme for a more polished look
_EXTRA_QSS = """
QTabBar::tab {
    padding: 9px 24px;
    font-size: 13px;
    min-width: 90px;
}
QPushButton {
    border-radius: 6px;
    padding: 5px 14px;
    min-height: 28px;
}
QLineEdit, QComboBox {
    border-radius: 6px;
    padding: 4px 8px;
    min-height: 26px;
}
QTextEdit {
    border-radius: 6px;
}
QScrollBar:vertical {
    width: 8px;
    border-radius: 4px;
    margin: 0;
}
QScrollBar::handle:vertical {
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { border-radius: 4px; }
QProgressBar::chunk { border-radius: 4px; }
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
    finished_signal = pyqtSignal(bool, str)  # success, error_message

    def __init__(self, task: Task):
        super().__init__()
        self.task = task

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
            downloader.download(
                log_callback=self.log_signal.emit,
                progress_callback=lambda cur, tot: self.progress_signal.emit(cur, tot),
            )
            self.finished_signal.emit(True, "")
        except Exception as e:
            self.finished_signal.emit(False, str(e))


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
    TaskStatus.PENDING: "#6c757d",
    TaskStatus.RUNNING: "#0d6efd",
    TaskStatus.COMPLETED: "#198754",
    TaskStatus.ERROR: "#dc3545",
}


class TaskCard(QFrame):
    run_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setObjectName("taskCard")
        self.setStyleSheet("""
            QFrame#taskCard {
                border: 1px solid rgba(255, 255, 255, 0.09);
                border-radius: 10px;
                background: rgba(255, 255, 255, 0.025);
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

        self.details_label = QLabel()
        self.details_label.setStyleSheet("color: #888; font-size: 12px;")
        info_col.addWidget(self.details_label)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #e55; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        info_col.addWidget(self.error_label)

        info_col.addStretch()
        top.addLayout(info_col, 1)

        self.status_label = QLabel()
        self.status_label.setFixedWidth(86)
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
        div = QFrame()
        div.setFrameShape(QFrame.Shape.HLine)
        div.setStyleSheet("color: rgba(255,255,255,0.06);")
        outer.addWidget(div)

        # --- Action buttons ---
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.run_btn = QPushButton("Run")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.setFixedHeight(30)
        self.run_btn.clicked.connect(lambda: self.run_requested.emit(self.task.id))
        btn_row.addWidget(self.run_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.edit_btn.setFixedHeight(30)
        self.edit_btn.clicked.connect(lambda: self.edit_requested.emit(self.task.id))
        btn_row.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFixedHeight(30)
        self.delete_btn.setStyleSheet("color: #e55;")
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self.task.id))
        btn_row.addWidget(self.delete_btn)

        btn_row.addStretch()

        self.log_toggle_btn = QPushButton("Logs")
        self.log_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_toggle_btn.setFixedHeight(30)
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

        color = _STATUS_COLORS.get(task.status, "#6c757d")
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
        self.run_btn.setEnabled(not running)
        self.edit_btn.setEnabled(not running)
        self.delete_btn.setEnabled(not running)

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
        self.setMinimumWidth(540)
        self._build_ui()
        if task:
            self._populate(task)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        title = QLabel("Edit Task" if self._existing else "Create Task")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("My task name")
        form.addRow("Name:", self.name_input)

        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText(
            "https://gallery-url-1.com/...\nhttps://gallery-url-2.com/...\n(One URL per line)"
        )
        self.urls_input.setFixedHeight(80)
        form.addRow("Gallery URLs:", self.urls_input)

        folder_row = QHBoxLayout()
        self.output_input = QLineEdit(str(Path("./downloads").resolve()))
        self.output_input.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.output_input)
        folder_row.addWidget(browse_btn)
        form.addRow("Output Folder:", folder_row)

        self.subfolder_checkbox = QCheckBox("Create a sub-folder")
        self.subfolder_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.subfolder_checkbox.setToolTip(
            "Keep each URL's downloads in its own sub-folder (named automatically\n"
            "by gallery-dl) instead of dumping every file into the output folder."
        )
        form.addRow("", self.subfolder_checkbox)

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

        cookies_row = QHBoxLayout()
        self.cookies_input = QLineEdit()
        self.cookies_input.setPlaceholderText("Optional — path to cookies.txt")
        self.cookies_input.setReadOnly(True)
        cookies_browse_btn = QPushButton("Browse")
        cookies_browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cookies_browse_btn.clicked.connect(self._browse_cookies)
        cookies_clear_btn = QPushButton("Clear")
        cookies_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cookies_clear_btn.clicked.connect(lambda: self.cookies_input.clear())
        cookies_row.addWidget(self.cookies_input)
        cookies_row.addWidget(cookies_browse_btn)
        cookies_row.addWidget(cookies_clear_btn)
        form.addRow("Cookies File:", cookies_row)

        self.auto_start_check = QCheckBox("Start automatically after creation")
        self.auto_start_check.setCursor(Qt.CursorShape.PointingHandCursor)
        form.addRow("", self.auto_start_check)

        layout.addLayout(form)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self.ok_btn = QPushButton("Save" if self._existing else "Create")
        self.ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_btn.setStyleSheet("font-weight: bold; padding: 6px 18px;")
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

    def _validate_and_accept(self):
        name = self.name_input.text().strip()
        urls = [u.strip() for u in self.urls_input.toPlainText().splitlines() if u.strip()]
        ok = True
        if not name:
            self.name_input.setStyleSheet("border: 1px solid #dc3545;")
            ok = False
        else:
            self.name_input.setStyleSheet("")
        if not urls:
            self.urls_input.setStyleSheet("border: 1px solid #dc3545;")
            ok = False
        else:
            self.urls_input.setStyleSheet("")
        if ok:
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
        layout.setContentsMargins(20, 16, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Tasks")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        create_btn = QPushButton("+ Create Task")
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setStyleSheet("font-weight: bold; padding: 7px 16px;")
        create_btn.clicked.connect(self._open_create_dialog)
        header.addWidget(create_btn)
        layout.addLayout(header)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._cards_widget = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_widget)
        self._cards_layout.setSpacing(10)
        self._cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._cards_layout.addStretch()
        scroll.setWidget(self._cards_widget)
        layout.addWidget(scroll)

    def _load_tasks(self):
        for task in self._manager.tasks:
            self._insert_card(task)

    def _insert_card(self, task: Task):
        card = TaskCard(task)
        card.run_requested.connect(self._run_task)
        card.edit_requested.connect(self._edit_task)
        card.delete_requested.connect(self._delete_task)
        self._cards[task.id] = card
        self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

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
            lambda ok, err, tid=task_id: self._on_finished(tid, ok, err)
        )
        self._workers[task_id] = worker
        worker.start()

    def _on_log(self, task_id: str, msg: str):
        card = self._cards.get(task_id)
        if card:
            card.append_log(msg)

    def _on_progress(self, task_id: str, current: int, total: int):
        card = self._cards.get(task_id)
        if card:
            card.update_progress(current, total)

    def _on_finished(self, task_id: str, success: bool, error_msg: str):
        task = self._manager.get(task_id)
        card = self._cards.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED if success else TaskStatus.ERROR
            task.error_message = error_msg if not success else None
            self._manager.update(task)
        if card:
            card.set_running(False)
            if task:
                card.update_task(task)
            card.append_log("\n✅ Task completed!" if success else f"\n❌ Task failed: {error_msg}")
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
        if task.status == TaskStatus.ERROR:
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

    def _delete_task(self, task_id: str):
        task = self._manager.get(task_id)
        if not task:
            return
        reply = QMessageBox.question(
            self, "Delete Task", f'Delete "{task.name}"?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        card = self._cards.pop(task_id, None)
        if card:
            card.setParent(None)
            card.deleteLater()
        self._manager.delete(task_id)


# ---------------------------------------------------------------------------
# Download tab
# ---------------------------------------------------------------------------


class DownloadTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Gallery Downloader")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

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
        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep)

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

        self.start_btn = QPushButton("Start Download")
        self.start_btn.setMinimumHeight(42)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self._start_download)
        layout.addWidget(self.start_btn)

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
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("gallery-dl Configuration")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Edit the gallery-dl config file. Changes apply to all downloads and tasks."
        )
        subtitle.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(subtitle)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep1)

        # --- File path row ---
        path_form = QFormLayout()
        path_form.setSpacing(10)
        path_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("No config file selected")
        self.path_input.setReadOnly(True)
        path_row.addWidget(self.path_input)

        browse_btn = QPushButton("Browse…")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
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

        self.create_btn = QPushButton("Create Default Config")
        self.create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.create_btn.setToolTip(
            "Runs: gallery-dl --config-create\n"
            "Creates a default config at ~/.config/gallery-dl/config.json"
        )
        self.create_btn.clicked.connect(self._create_default_config)
        actions_row.addWidget(self.create_btn)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.clicked.connect(self._open_folder)
        actions_row.addWidget(self.open_folder_btn)

        layout.addLayout(actions_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: rgba(255,255,255,0.08);")
        layout.addWidget(sep2)

        # --- JSON editor ---
        editor_label = QLabel("Config content (JSON):")
        editor_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(editor_label)

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

        reload_btn = QPushButton("Reload")
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.clicked.connect(self._load_config)
        bottom_row.addWidget(reload_btn)

        save_btn = QPushButton("Save")
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet("font-weight: bold; padding: 5px 18px;")
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
            self.status_label.setStyleSheet("font-size: 12px; color: #198754;")
            try:
                self.editor.setPlainText(config_path.read_text())
            except Exception as e:
                self.editor.setPlainText(f"# Could not read file: {e}")
        else:
            self.path_input.setText("")
            self.status_label.setText("✘ No config file found")
            self.status_label.setStyleSheet("font-size: 12px; color: #dc3545;")
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
        folder = str(config_path.parent)
        for cmd in (["xdg-open", folder], ["dolphin", folder], ["nautilus", folder]):
            try:
                subprocess.Popen(cmd, env=subprocess_env())
                return
            except FileNotFoundError:
                continue

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
            self.status_label.setStyleSheet("font-size: 12px; color: #198754;")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gallery Downloader")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(740, 640)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(TasksTab(), "Tasks")
        tabs.addTab(DownloadTab(), "Download")
        tabs.addTab(ConfigTab(), "Config")
        layout.addWidget(tabs)


def launch_gui():
    import sys

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    qdarktheme.setup_theme("auto", additional_qss=_EXTRA_QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
