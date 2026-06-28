import subprocess
from pathlib import Path

import qdarktheme
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models.downloader.downloader import Downloader


class DownloadWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(
        self, output_folder, urls, target_format, override_format, archive_format
    ):
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
            )
            downloader.download(log_callback=self.log_signal.emit)
            self.log_signal.emit("\n✅ All downloads complete!")
        except Exception as e:
            self.log_signal.emit(f"\n❌ Fatal Error: {str(e)}")
        finally:
            self.finished_signal.emit()


def _pick_folder_native(start_path: str) -> str | None:
    """Open a native OS folder picker, preferring kdialog on KDE, falling back to zenity."""
    for cmd in (
        ["kdialog", "--getexistingdirectory", start_path],
        ["zenity", "--file-selection", "--directory", f"--filename={start_path}/"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            # Binary found — honour the result (cancelled = empty, confirmed = path)
            return result.stdout.strip() or None
        except FileNotFoundError:
            continue  # binary not installed, try next

    return None


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Gallery Downloader")
        self.resize(650, 550)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("Gallery Downloader")
        title_label.setStyleSheet(
            "font-size: 20px; font-weight: bold; margin-bottom: 10px;"
        )
        main_layout.addWidget(title_label)

        form_layout = QFormLayout()
        form_layout.setSpacing(15)

        self.urls_input = QTextEdit()
        self.urls_input.setPlaceholderText(
            "https://gallery-url-1.com/...\nhttps://gallery-url-2.com/...\n(One URL per line)"
        )
        self.urls_input.setFixedHeight(80)
        form_layout.addRow("Gallery URLs:", self.urls_input)

        folder_layout = QHBoxLayout()
        self.output_input = QLineEdit(str(Path("./downloads").resolve()))
        self.output_input.setReadOnly(True)
        browse_btn = QPushButton("Browse")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.clicked.connect(self.browse_folder)
        folder_layout.addWidget(self.output_input)
        folder_layout.addWidget(browse_btn)
        form_layout.addRow("Output Folder:", folder_layout)

        format_layout = QHBoxLayout()
        self.target_format_combo = QComboBox()
        self.target_format_combo.addItems(["gif", "mp4", "webm", "mkv"])

        self.override_checkbox = QCheckBox("Force conversion (Override)")
        self.override_checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        self.override_checkbox.setToolTip(
            "Force conversion even if duration/audio rules are not met."
        )

        format_layout.addWidget(self.target_format_combo)
        format_layout.addWidget(self.override_checkbox)
        format_layout.addStretch()
        form_layout.addRow("Target Format:", format_layout)

        self.archive_combo = QComboBox()
        self.archive_combo.addItems(["None", "zip", "cbz", "rar", "cbr"])
        self.archive_combo.setFixedWidth(150)
        form_layout.addRow("Archive Mode:", self.archive_combo)

        main_layout.addLayout(form_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(line)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-family: monospace; font-size: 13px;")
        main_layout.addWidget(self.log_area)

        self.start_btn = QPushButton("Start Download")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.start_btn.clicked.connect(self.start_download)
        main_layout.addWidget(self.start_btn)

    def browse_folder(self):
        folder = _pick_folder_native(self.output_input.text())
        if folder:
            self.output_input.setText(folder)

    def append_log(self, text):
        self.log_area.append(text)
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def start_download(self):
        raw_text = self.urls_input.toPlainText()
        urls = [line.strip() for line in raw_text.splitlines() if line.strip()]

        if not urls:
            self.append_log("⚠️ Error: Please enter at least one valid URL.")
            return

        self.start_btn.setEnabled(False)
        self.start_btn.setText("Processing...")

        selected_archive = self.archive_combo.currentText()
        archive_val = selected_archive if selected_archive != "None" else None

        self.append_log(f"⏳ Starting download for {len(urls)} URL(s)...")

        self.worker = DownloadWorker(
            output_folder=self.output_input.text(),
            urls=urls,
            target_format=self.target_format_combo.currentText(),
            override_format=self.override_checkbox.isChecked(),
            archive_format=archive_val,
        )
        self.worker.log_signal.connect(self.append_log)
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.start()

    def download_finished(self):
        self.start_btn.setEnabled(True)
        self.start_btn.setText("Start Download")


def launch_gui():
    import sys

    app = QApplication(sys.argv)
    qdarktheme.setup_theme("auto")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
