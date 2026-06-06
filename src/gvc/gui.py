from __future__ import annotations

import html
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QComboBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QCheckBox,
    QProgressBar,
)

from gvc.atlas import generate_sprite_atlas
from gvc.convert import ConvertOptions, ENGINE_PROFILES, convert_video, ogv_modes_for_profile
from gvc.ffmpeg_paths import FFmpegNotFoundError, resolve_ffmpeg_and_ffprobe
from gvc import __version__
from gvc.i18n import LANGUAGE_LABELS, language_label_to_code, translate_runtime_error, ui_text
from gvc.probe import probe_video
from gvc.settings import AppSettings, load_settings, save_settings


def _project_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _app_icon() -> QIcon:
    root = _project_root()
    candidates = [root / "Assets" / "icon.ico", root / "Assets" / "icon.png"]
    for path in candidates:
        if path.exists():
            return QIcon(str(path))
    return QIcon()


def _dark_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(32, 34, 39))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(236, 239, 244))
    palette.setColor(QPalette.ColorRole.Base, QColor(24, 26, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(39, 43, 51))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(24, 26, 30))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(236, 239, 244))
    palette.setColor(QPalette.ColorRole.Text, QColor(236, 239, 244))
    palette.setColor(QPalette.ColorRole.Button, QColor(47, 52, 62))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(236, 239, 244))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 107, 107))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(88, 166, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(17, 21, 28))
    palette.setColor(QPalette.ColorRole.Link, QColor(88, 166, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(128, 134, 145))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(128, 134, 145))
    return palette


def _apply_default_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())


def _html_list(items: list[str]) -> str:
    if not items:
        return ""
    return "<ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in items) + "</ul>"


class Worker(QObject):
    progress = Signal(int)
    status = Signal(object)
    done = Signal(bool)

    def __init__(self, fn, cancel_event: Event):
        super().__init__()
        self._fn = fn
        self._cancel_event = cancel_event

    def run(self):
        try:
            self._fn(self._cancel_event, self.progress.emit, self.status.emit)
            self.done.emit(True)
        except Exception as exc:
            if self._cancel_event.is_set() or "cancel" in str(exc).lower():
                self.status.emit({"key": "cancelled", "kwargs": {}})
            else:
                self.status.emit({"error": str(exc)})
            self.done.emit(False)


class MainWindow(QMainWindow):
    VIDEO_EXTENSIONS = {
        ".mp4",
        ".m4v",
        ".mov",
        ".mkv",
        ".avi",
        ".webm",
        ".ogv",
        ".ogg",
        ".wmv",
        ".flv",
        ".mpg",
        ".mpeg",
        ".3gp",
        ".gif",
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Godot Video Converter")
        self.setWindowIcon(_app_icon())
        self.resize(1320, 860)
        self.setAcceptDrops(True)

        self.ffmpeg, self.ffprobe = resolve_ffmpeg_and_ffprobe()
        self._thread: QThread | None = None
        self._worker: Worker | None = None
        self._cancel_event: Event | None = None
        self._loading_settings = False
        self._probe_cache = {}
        self._status_key: str | None = "ready"
        self._status_kwargs: dict[str, object] = {}
        self._status_text_override: str | None = None
        self._progress_started = False
        self._progress_error_state = False
        self._close_after_cancel = False
        self._output_validation_timer = QTimer(self)
        self._output_validation_timer.setInterval(4000)
        self._output_validation_timer.timeout.connect(self._ensure_output_directory_silent)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.setHandleWidth(14)
        layout.addWidget(self.content_splitter, 1)

        left_panel = QWidget()
        left = QVBoxLayout(left_panel)
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(8)
        self.content_splitter.addWidget(left_panel)

        files_row = QHBoxLayout()
        files_row.setSpacing(8)
        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.ExtendedSelection)
        files_btns = QVBoxLayout()
        files_btns.setSpacing(8)
        self.btn_add = QPushButton("Add Files")
        self.btn_remove = QPushButton("Remove Selected")
        self.btn_clear = QPushButton("Clear")
        self.btn_add.setMinimumWidth(140)
        self.btn_remove.setMinimumWidth(140)
        self.btn_clear.setMinimumWidth(140)
        files_btns.addWidget(self.btn_add)
        files_btns.addWidget(self.btn_remove)
        files_btns.addWidget(self.btn_clear)
        files_btns.addStretch()
        files_row.addWidget(self.files, 1)
        files_row.addLayout(files_btns)
        left.addLayout(files_row)

        out_row = QHBoxLayout()
        out_row.setSpacing(8)
        self.output = QLineEdit(str(Path.cwd() / "output"))
        self.btn_output_change = QPushButton("Change Output")
        self.btn_output_open = QPushButton("Open Output")
        self.btn_about = QPushButton("About")
        self.language = QComboBox()
        self.language.addItems(list(LANGUAGE_LABELS))
        self.language.setMinimumWidth(120)
        self.output_label = QLabel("Output:")
        self.language_label = QLabel("Language:")
        out_row.addWidget(self.output_label)
        out_row.addWidget(self.output, 1)
        out_row.addWidget(self.btn_output_change)
        out_row.addWidget(self.btn_output_open)
        out_row.addWidget(self.language_label)
        out_row.addWidget(self.language)
        out_row.addWidget(self.btn_about)
        left.addLayout(out_row)

        self.tabs = QTabWidget()
        left.addWidget(self.tabs)

        convert_tab = QWidget()
        convert_layout = QVBoxLayout(convert_tab)

        row1 = QGridLayout()
        row1.setHorizontalSpacing(10)
        row1.setVerticalSpacing(10)
        self.format = QComboBox()
        self.format.addItems(["ogv", "mp4", "webm", "gif"])
        self.format.setMinimumWidth(130)
        self.quality = QComboBox()
        self.quality.addItems(["ultra", "high", "balanced", "optimized", "tiny"])
        self.quality.setMinimumWidth(130)
        self.resolution = QComboBox()
        self.resolution.setEditable(True)
        self.resolution.setMinimumWidth(170)
        self.resolution.addItems(
            [
                "Keep original",
                "256x144",
                "320x180",
                "320x240",
                "426x240",
                "480x270",
                "512x288",
                "640x360",
                "640x480",
                "720x404",
                "720x480",
                "768x432",
                "854x480",
                "960x540",
                "1024x576",
                "1024x768",
                "1152x648",
                "1280x720",
                "1280x960",
                "1366x768",
                "1600x900",
                "1920x1080",
                "2560x1440",
                "3840x2160",
            ]
        )
        self.resolution.setCurrentText("Keep original")
        self.fps = QDoubleSpinBox()
        self.fps.setRange(1.0, 60.0)
        self.fps.setDecimals(2)
        self.fps.setSingleStep(1.0)
        self.fps.setValue(30.0)
        self.fps.setMinimumWidth(95)
        self.format_label = QLabel("Format")
        self.quality_label = QLabel("Quality")
        self.resolution_label = QLabel("Resolution")
        self.fps_label = QLabel("FPS")
        row1.addWidget(self.format_label, 0, 0)
        row1.addWidget(self.format, 0, 1)
        row1.addWidget(self.quality_label, 0, 2)
        row1.addWidget(self.quality, 0, 3)
        row1.addWidget(self.resolution_label, 0, 4)
        row1.addWidget(self.resolution, 0, 5)
        row1.addWidget(self.fps_label, 0, 6)
        row1.addWidget(self.fps, 0, 7)
        row1.setColumnStretch(1, 1)
        row1.setColumnStretch(3, 1)
        row1.setColumnStretch(5, 1)
        convert_layout.addLayout(row1)

        self.format_hint = QLabel()
        self.format_hint.setWordWrap(True)
        self.format_hint.setTextFormat(Qt.TextFormat.RichText)
        convert_layout.addWidget(self.format_hint)

        row2 = QGridLayout()
        row2.setHorizontalSpacing(10)
        row2.setVerticalSpacing(10)
        self.engine_profile_label = QLabel("Engine Profile")
        self.engine_profile = QComboBox()
        self.engine_profile.addItems(list(ENGINE_PROFILES))
        self.engine_profile.setMinimumWidth(150)
        self.keep_audio = QCheckBox("Keep audio")
        self.ogv_mode_label = QLabel("OGV mode")
        self.ogv_mode = QComboBox()
        self.ogv_mode.setMinimumWidth(240)
        self._reload_ogv_mode_options("Godot")
        row2.addWidget(self.engine_profile_label, 0, 0)
        row2.addWidget(self.engine_profile, 0, 1)
        row2.addWidget(self.keep_audio, 0, 2)
        row2.addWidget(self.ogv_mode_label, 0, 3)
        row2.addWidget(self.ogv_mode, 0, 4, 1, 3)
        row2.setColumnStretch(4, 1)
        convert_layout.addLayout(row2)

        self.preset_group = QGroupBox()
        preset_layout = QVBoxLayout(self.preset_group)
        self.preset_title = QLabel()
        self.preset_title.setWordWrap(True)
        self.preset_body = QLabel()
        self.preset_body.setWordWrap(True)
        self.preset_body.setTextFormat(Qt.TextFormat.RichText)
        preset_layout.addWidget(self.preset_title)
        preset_layout.addWidget(self.preset_body)
        convert_layout.addWidget(self.preset_group)

        actions_row = QHBoxLayout()
        self.btn_action = QPushButton("Convert Video")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setEnabled(False)
        actions_row.addWidget(self.btn_action)
        actions_row.addWidget(self.btn_cancel)
        actions_row.addStretch()
        left.addLayout(actions_row)

        atlas_tab = QWidget()
        atlas_layout = QVBoxLayout(atlas_tab)

        arow1 = QHBoxLayout()
        self.atlas_fps = QSpinBox()
        self.atlas_fps.setRange(1, 30)
        self.atlas_fps.setValue(5)
        self.atlas_mode = QComboBox()
        self.atlas_res = QComboBox()
        self.frames_label = QLabel("Frames")
        self.mode_label = QLabel("Mode")
        self.atlas_resolution_label = QLabel("Resolution")
        arow1.addWidget(self.frames_label)
        arow1.addWidget(self.atlas_fps)
        arow1.addWidget(self.mode_label)
        arow1.addWidget(self.atlas_mode)
        arow1.addWidget(self.atlas_resolution_label)
        arow1.addWidget(self.atlas_res)
        arow1.addStretch()
        atlas_layout.addLayout(arow1)

        self.tabs.addTab(convert_tab, "Convert Video")
        self.tabs.addTab(atlas_tab, "Generate Atlas")

        right_panel = QWidget()
        right = QVBoxLayout(right_panel)
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(8)
        self.content_splitter.addWidget(right_panel)
        self.content_splitter.setStretchFactor(0, 2)
        self.content_splitter.setStretchFactor(1, 3)
        self.content_splitter.setSizes([540, 940])

        self.rec_group = QGroupBox("Godot Recommendations")
        rec_group_layout = QVBoxLayout(self.rec_group)
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(320)
        self.summary_text.setAcceptRichText(True)
        self.guidance_text = QTextEdit()
        self.guidance_text.setReadOnly(True)
        self.guidance_text.setMinimumHeight(290)
        self.guidance_text.setAcceptRichText(True)
        rec_group_layout.addWidget(self.summary_text)
        rec_group_layout.addWidget(self.guidance_text, 1)
        right.addWidget(self.rec_group, 1)

        self.progress = QProgressBar()
        self.status = QLabel("Ready")
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

        self.btn_add.clicked.connect(self.on_add_files)
        self.btn_remove.clicked.connect(self.on_remove_selected)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_output_change.clicked.connect(self.on_output_dir)
        self.btn_output_open.clicked.connect(self.on_open_output_dir)
        self.btn_about.clicked.connect(self.on_about)
        self.btn_action.clicked.connect(self.on_action)
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.tabs.currentChanged.connect(self._update_action_button)
        self.language.currentTextChanged.connect(self.on_language_changed)

        self.files.itemSelectionChanged.connect(self.refresh_selected_info)

        self.output.textChanged.connect(self.save_ui_settings)
        self.output.textChanged.connect(self._refresh_experience_panels)
        self.output.editingFinished.connect(self._validate_output_directory_from_ui)
        self.engine_profile.currentTextChanged.connect(self.on_engine_profile_changed)
        self.format.currentTextChanged.connect(self.save_ui_settings)
        self.format.currentTextChanged.connect(self._update_ogv_mode_state)
        self.format.currentTextChanged.connect(self.refresh_selected_info)
        self.quality.currentTextChanged.connect(self.save_ui_settings)
        self.quality.currentTextChanged.connect(self._refresh_experience_panels)
        self.resolution.currentTextChanged.connect(self.save_ui_settings)
        self.resolution.currentTextChanged.connect(self._refresh_experience_panels)
        self.fps.valueChanged.connect(self.save_ui_settings)
        self.fps.valueChanged.connect(self._refresh_experience_panels)
        self.keep_audio.toggled.connect(self.save_ui_settings)
        self.keep_audio.toggled.connect(self.refresh_selected_info)
        self.ogv_mode.currentTextChanged.connect(self.save_ui_settings)
        self.ogv_mode.currentTextChanged.connect(self._refresh_experience_panels)
        self.atlas_fps.valueChanged.connect(self.save_ui_settings)
        self.atlas_mode.currentTextChanged.connect(self.save_ui_settings)
        self.atlas_res.currentTextChanged.connect(self.save_ui_settings)

        self._load_ui_settings()
        self._ensure_output_directory_silent()
        self._apply_language()
        self._update_action_button()
        self._update_ogv_mode_state()
        self._output_validation_timer.start()

    def _on_worker_done(self, ok: bool) -> None:
        self._set_busy(False)
        if ok and not (self._cancel_event and self._cancel_event.is_set()):
            self._set_status_key("done")
        elif self._cancel_event and self._cancel_event.is_set():
            self._set_status_key("cancelled")
        else:
            self._freeze_progress_bar_on_error()

        if self._thread:
            self._thread.quit()
            self._thread.wait()

        self._thread = None
        self._worker = None
        self._cancel_event = None

        if self._close_after_cancel:
            self._close_after_cancel = False
            self.close()

    def _current_output_path(self) -> Path:
        return Path(self.output.text().strip() or "output")

    def _ensure_output_directory(self, *, notify: bool = False) -> Path | None:
        output = self._current_output_path()
        try:
            if output.exists() and not output.is_dir():
                raise NotADirectoryError(f"Output path is not a directory: {output}")
            output.mkdir(parents=True, exist_ok=True)
            return output
        except OSError as exc:
            if notify:
                QMessageBox.warning(self, self._tr("open_output_folder"), str(exc))
            return None

    def _ensure_output_directory_silent(self) -> None:
        self._ensure_output_directory(notify=False)

    def _validate_output_directory_from_ui(self) -> None:
        self._ensure_output_directory(notify=True)

    def _set_status_text(self, text: str) -> None:
        self._status_key = None
        self._status_kwargs = {}
        self._status_text_override = text
        self.status.setText(text)

    def _set_status_key(self, key: str, **kwargs) -> None:
        self._status_key = key
        self._status_kwargs = kwargs
        self._status_text_override = None
        self.status.setText(self._tr(key, **kwargs))

    def _refresh_status_label(self) -> None:
        if self._status_key is not None:
            self.status.setText(self._tr(self._status_key, **self._status_kwargs))
            return
        if self._status_text_override is not None:
            self.status.setText(self._status_text_override)

    def _handle_worker_status(self, payload: object) -> None:
        if isinstance(payload, dict) and "key" in payload:
            self._set_status_key(str(payload["key"]), **dict(payload.get("kwargs") or {}))
            return
        if isinstance(payload, dict) and "error" in payload:
            raw = str(payload["error"])
            translated = translate_runtime_error(raw, self.language.currentText())
            self._set_status_text(self._tr("error_prefix", message=translated))
            return
        if isinstance(payload, dict) and "text" in payload:
            self._set_status_text(str(payload["text"]))
            return
        self._set_status_text(str(payload))

    def _set_progress_error_state(self, enabled: bool) -> None:
        self._progress_error_state = enabled
        if enabled:
            self.progress.setStyleSheet(
                "QProgressBar {"
                " border: 1px solid #6b2d2d;"
                " border-radius: 4px;"
                " background-color: #241818;"
                " text-align: center;"
                " color: #f3d6d6;"
                "}"
                "QProgressBar::chunk {"
                " background-color: #d9534f;"
                "}"
            )
            return
        self.progress.setStyleSheet("")

    def _reset_progress_bar(self, indeterminate: bool = False) -> None:
        self._progress_started = False
        self._set_progress_error_state(False)
        if indeterminate:
            self.progress.setRange(0, 0)
            self.progress.setValue(0)
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _freeze_progress_bar_on_error(self) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._set_progress_error_state(True)

    def _handle_worker_progress(self, value: int) -> None:
        if not self._progress_started:
            self._progress_started = True
            self.progress.setRange(0, 100)
        self.progress.setValue(value)

    def _is_heavy_video(self, info) -> bool:
        if not info or not getattr(info, "is_valid", False):
            return False
        return (
            info.width >= 3840
            or info.height >= 2160
            or info.frame_rate >= 50
            or (info.width >= 2560 and info.frame_rate >= 30)
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self._add_files(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread and self._thread.isRunning():
            if self._close_after_cancel:
                event.ignore()
                return
            choice = QMessageBox.question(
                self,
                self._tr("operation_in_progress"),
                self._tr("operation_in_progress_text"),
            )
            if choice != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._close_after_cancel = True
            self.on_cancel()
            event.ignore()
            return
        event.accept()

    def _load_ui_settings(self) -> None:
        self._loading_settings = True
        s = load_settings()
        self._set_combo_value(self.language, s.selected_language, "English")
        self.output.setText(s.output_folder or str(Path.cwd() / "output"))
        self._set_combo_value(self.engine_profile, s.selected_engine_profile, "Godot")
        self._set_combo_value(self.format, s.selected_format, "ogv")
        self._set_combo_value(self.quality, s.selected_quality, "optimized")
        self._set_editable_combo_value(self.resolution, s.selected_resolution, "Keep original")
        self.fps.setValue(self._coerce_video_fps(s.fps))
        self.keep_audio.setChecked(s.keep_audio)
        self._reload_ogv_mode_options(self.engine_profile.currentText(), s.selected_ogv_mode)
        self.atlas_fps.setValue(max(1, min(30, s.atlas_fps or 5)))
        self._reload_atlas_mode_options(s.selected_atlas_mode)
        self._reload_atlas_resolution_options(s.selected_atlas_resolution)
        self._loading_settings = False

    def _set_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        fallback_idx = combo.findText(fallback)
        if fallback_idx >= 0:
            combo.setCurrentIndex(fallback_idx)

    def _set_editable_combo_value(self, combo: QComboBox, value: str, fallback: str) -> None:
        chosen = (value or "").strip() or fallback
        idx = combo.findText(chosen)
        if idx >= 0:
            combo.setCurrentIndex(idx)
            return
        combo.setCurrentText(chosen)

    def _ogv_mode_value(self) -> str:
        data = self.ogv_mode.currentData()
        if isinstance(data, str) and data.strip():
            return data
        return self.ogv_mode.currentText().strip()

    def _atlas_mode_value(self) -> str:
        data = self.atlas_mode.currentData()
        if isinstance(data, str) and data.strip():
            return data
        return self.atlas_mode.currentText().strip().lower()

    def _atlas_resolution_value(self) -> str:
        data = self.atlas_res.currentData()
        if isinstance(data, str) and data.strip():
            return data
        return self.atlas_res.currentText().strip()

    def _ogv_mode_title_key(self, mode: str) -> str:
        mode_key = (mode or "").strip().lower()
        return {
            "official godot": "preset_official_godot_title",
            "seek friendly": "preset_seek_friendly_title",
            "ideal loop": "preset_ideal_loop_title",
            "mobile optimized": "preset_mobile_optimized_title",
            "high compression": "preset_high_compression_title",
            "love2d compatibility": "preset_love2d_compatibility_title",
            "lightweight": "preset_lightweight_title",
        }.get(mode_key, "")

    def _ogv_mode_label(self, mode: str) -> str:
        title_key = self._ogv_mode_title_key(mode)
        if title_key:
            return self._tr(title_key)
        return mode

    def _reload_atlas_mode_options(self, selected: str | None = None) -> None:
        current = (selected if selected is not None else self._atlas_mode_value()).strip().lower()
        options = [
            ("grid", self._tr("atlas_mode_grid")),
            ("horizontal", self._tr("atlas_mode_horizontal")),
            ("vertical", self._tr("atlas_mode_vertical")),
        ]
        self.atlas_mode.blockSignals(True)
        self.atlas_mode.clear()
        for value, label in options:
            self.atlas_mode.addItem(label, value)
        idx = self.atlas_mode.findData(current)
        self.atlas_mode.setCurrentIndex(idx if idx >= 0 else 0)
        self.atlas_mode.blockSignals(False)

    def _reload_atlas_resolution_options(self, selected: str | None = None) -> None:
        current = (selected if selected is not None else self._atlas_resolution_value()).strip()
        options = [
            ("Low", self._tr("atlas_resolution_low")),
            ("Medium", self._tr("atlas_resolution_medium")),
            ("High", self._tr("atlas_resolution_high")),
        ]
        self.atlas_res.blockSignals(True)
        self.atlas_res.clear()
        for value, label in options:
            self.atlas_res.addItem(label, value)
        idx = self.atlas_res.findData(current)
        self.atlas_res.setCurrentIndex(idx if idx >= 0 else 1)
        self.atlas_res.blockSignals(False)

    def save_ui_settings(self) -> None:
        if self._loading_settings:
            return
        s = AppSettings(
            selected_language=self.language.currentText(),
            output_folder=self.output.text().strip() or "output",
            selected_engine_profile=self.engine_profile.currentText(),
            selected_format=self.format.currentText(),
            selected_resolution=self.resolution.currentText().strip() or "Keep original",
            selected_quality=self.quality.currentText(),
            selected_ogv_mode=self._ogv_mode_value(),
            keep_audio=self.keep_audio.isChecked(),
            fps=f"{self.fps.value():g}",
            atlas_fps=self.atlas_fps.value(),
            selected_atlas_mode=self._atlas_mode_value(),
            selected_atlas_resolution=self._atlas_resolution_value(),
        )
        try:
            save_settings(s)
        except OSError as exc:
            print(f"Warning: failed to save settings: {exc}", file=sys.stderr)

    def _tr(self, key: str, **kwargs) -> str:
        lang = self.language.currentText() if hasattr(self, "language") else LANGUAGE_LABELS[0]
        return ui_text(lang, key, **kwargs)

    def _lang_code(self) -> str:
        return language_label_to_code(self.language.currentText())

    def _all_translations(self, key: str) -> set[str]:
        return {ui_text(label, key) for label in LANGUAGE_LABELS}

    def _selected_primary_path(self) -> str | None:
        items = self.files.selectedItems()
        if items:
            return items[0].text()
        if self.files.count() > 0:
            return self.files.item(0).text()
        return None

    def _selected_video_info(self):
        src = self._selected_primary_path()
        if not src:
            return None
        try:
            return self._cached_probe(src)
        except Exception:
            return None

    def _engine_key(self) -> str:
        return "love2d" if self.engine_profile.currentText().strip().lower() == "love2d" else "godot"

    def _format_key(self) -> str:
        return self.format.currentText().strip().lower()

    def _current_preset_summary(self) -> tuple[str, str]:
        engine = self._engine_key()
        fmt = self._format_key()
        if fmt != "ogv":
            return (
                self._tr(f"format_{fmt}_title"),
                self._tr(f"format_{fmt}_body"),
            )

        mode = self._ogv_mode_value().strip().lower()
        preset_map = {
            "official godot": ("preset_official_godot_title", "preset_official_godot_body"),
            "seek friendly": ("preset_seek_friendly_title", "preset_seek_friendly_body"),
            "ideal loop": ("preset_ideal_loop_title", "preset_ideal_loop_body"),
            "mobile optimized": ("preset_mobile_optimized_title", "preset_mobile_optimized_body"),
            "high compression": ("preset_high_compression_title", "preset_high_compression_body"),
            "love2d compatibility": ("preset_love2d_compatibility_title", "preset_love2d_compatibility_body"),
            "lightweight": ("preset_lightweight_title", "preset_lightweight_body"),
        }
        title_key, body_key = preset_map.get(
            mode,
            (
                f"preset_{engine}_default_title",
                f"preset_{engine}_default_body",
            ),
        )
        return self._tr(title_key), self._tr(body_key)

    def _estimate_levels(self, info) -> tuple[str, str, str]:
        fmt = self._format_key()
        quality = self.quality.currentText().strip().lower()
        fps = float(self.fps.value())
        resolution = self.resolution.currentText().strip().lower()
        duration = info.duration if info and getattr(info, "is_valid", False) else 0.0
        ogv_mode = self._ogv_mode_value().strip().lower()

        score = 0
        if fmt == "ogv":
            score += 3
        elif fmt == "webm":
            score += 2
        elif fmt == "mp4":
            score += 1

        score += {"ultra": 3, "high": 2, "balanced": 1, "optimized": 0, "tiny": -1}.get(quality, 0)
        if fmt == "ogv":
            score += {
                "ideal loop": 2,
                "seek friendly": 1,
                "official godot": 1,
                "love2d compatibility": 1,
                "mobile optimized": 0,
                "lightweight": -1,
                "high compression": -1,
            }.get(ogv_mode, 0)
        if fps > 30:
            score += 1
        if fps <= 20:
            score -= 1
        if resolution not in {"", self._tr("keep_original").lower(), "keep original"}:
            if "1920x1080" in resolution or "2560x" in resolution or "3840x" in resolution:
                score += 2
            elif "1280x720" in resolution or "1366x768" in resolution:
                score += 1
            elif "640x" in resolution or "854x480" in resolution or "480x" in resolution:
                score -= 1
        elif info and getattr(info, "is_valid", False):
            if info.width >= 1920 or info.height >= 1080:
                score += 2
            elif info.width <= 854 and info.height <= 480:
                score -= 1
        if duration > 90:
            score += 1

        if score >= 5:
            speed = self._tr("estimate_slow")
            size = self._tr("estimate_large")
        elif score >= 2:
            speed = self._tr("estimate_medium")
            size = self._tr("estimate_medium")
        else:
            speed = self._tr("estimate_fast")
            size = self._tr("estimate_small")

        if fmt == "ogv":
            compatibility = self._tr("estimate_best")
        elif fmt == "mp4":
            compatibility = self._tr("estimate_general")
        elif fmt == "webm":
            compatibility = self._tr("estimate_good")
        else:
            compatibility = self._tr("estimate_preview")
        return compatibility, speed, size

    def _summary_expectation(self) -> str:
        engine = self._engine_key()
        fmt = self._format_key()
        if fmt == "ogv":
            mode = self._ogv_mode_value().strip().lower()
            if mode == "ideal loop":
                return self._tr("expect_loop")
            if mode == "seek friendly":
                return self._tr("expect_seek")
            if mode in {"mobile optimized", "love2d compatibility"}:
                return self._tr("expect_safe")
            if mode in {"high compression", "lightweight"}:
                return self._tr("expect_small")
            return self._tr("expect_engine_default", engine=self.engine_profile.currentText())
        if fmt == "mp4":
            return self._tr("expect_mp4")
        if fmt == "webm":
            return self._tr("expect_webm")
        return self._tr("expect_gif")

    def _resolution_for_summary(self, info) -> str:
        current = self.resolution.currentText().strip()
        if current and current not in self._all_translations("keep_original"):
            return current
        if info and getattr(info, "is_valid", False):
            return f"{info.width}x{info.height}"
        return self._tr("keep_original")

    def _output_preview_name(self) -> str:
        path = self._selected_primary_path()
        stem = Path(path).stem if path else "video"
        suffix_map = {"ogv": ".ogv", "mp4": ".mp4", "webm": ".webm", "gif": ".gif"}
        return f"{stem}_converted{suffix_map.get(self._format_key(), '.ogv')}"

    def _render_summary_html(self, info) -> str:
        title, body = self._current_preset_summary()
        source_name = Path(self._selected_primary_path()).name if self._selected_primary_path() else self._tr("no_file_selected")
        items = [
            f"{self._tr('summary_engine')}: {self.engine_profile.currentText()}",
            f"{self._tr('summary_target')}: {self.format.currentText()}",
            f"{self._tr('summary_preset')}: {title}",
            f"{self._tr('summary_resolution')}: {self._resolution_for_summary(info)}",
            f"{self._tr('summary_fps')}: {self.fps.value():g}",
            f"{self._tr('summary_audio')}: {self._tr('audio_kept') if self.keep_audio.isChecked() else self._tr('audio_removed')}",
            f"{self._tr('summary_output_file')}: {Path(self.output.text().strip() or 'output') / self._output_preview_name()}",
        ]
        return (
            f"<h3>{html.escape(self._tr('summary_title'))}</h3>"
            f"<p><b>{html.escape(source_name)}</b></p>"
            f"{_html_list(items)}"
            f"<p><b>{html.escape(self._tr('summary_expectation'))}</b> {html.escape(self._summary_expectation())}</p>"
        )

    def _recommendation_bullets(self, info) -> tuple[list[str], list[str], list[str]]:
        if not info or not getattr(info, "is_valid", False):
            return [], [], []

        what_has: list[str] = []
        risks: list[str] = []
        next_step: list[str] = []

        if info.duration <= 10:
            what_has.append(self._tr("insight_short_clip"))
        elif info.duration <= 60:
            what_has.append(self._tr("insight_medium_clip"))
        else:
            what_has.append(self._tr("insight_long_clip"))
            risks.append(self._tr("risk_long_clip"))

        if info.width >= 1920 or info.height >= 1080:
            what_has.append(self._tr("insight_high_res"))
            risks.append(self._tr("risk_large_ogv"))
        elif info.width <= 854 and info.height <= 480:
            what_has.append(self._tr("insight_low_res"))
        else:
            what_has.append(self._tr("insight_standard_res"))

        if info.frame_rate > 30:
            risks.append(self._tr("risk_high_fps"))
        elif info.frame_rate < 20:
            risks.append(self._tr("risk_low_fps"))
        else:
            what_has.append(self._tr("insight_practical_fps"))

        if info.has_audio:
            what_has.append(self._tr("insight_has_audio"))
            if not self.keep_audio.isChecked():
                risks.append(self._tr("risk_audio_removed"))
        else:
            what_has.append(self._tr("insight_no_audio"))

        next_step.append(self._summary_expectation())
        if self._format_key() != "ogv":
            next_step.append(self._tr("next_try_ogv"))
        else:
            next_step.append(self._tr("next_keep_current_preset"))

        if self._format_key() == "ogv" and self.quality.currentText().strip().lower() in {"ultra", "high"}:
            next_step.append(self._tr("next_if_need_smaller"))
        elif self._format_key() == "ogv":
            next_step.append(self._tr("next_if_need_more_quality"))
        return what_has, risks, next_step

    def _render_guidance_html(self, info) -> str:
        title, body = self._current_preset_summary()
        what_has, risks, next_step = self._recommendation_bullets(info)
        if not what_has and not risks and not next_step:
            return f"<p>{html.escape(self._tr('no_recommendations'))}</p>"
        sections = [
            f"<h3>{html.escape(self._tr('guide_source_title'))}</h3>{_html_list(what_has)}",
            f"<h3>{html.escape(self._tr('guide_preset_title', preset=title))}</h3><p>{html.escape(body)}</p>",
            f"<h3>{html.escape(self._tr('guide_next_title'))}</h3>{_html_list(next_step)}",
        ]
        if risks:
            sections.insert(1, f"<h3>{html.escape(self._tr('guide_risks_title'))}</h3>{_html_list(risks)}")
        return "".join(sections)

    def _refresh_experience_panels(self, *_args, invalid_video_name: str | None = None) -> None:
        title, body = self._current_preset_summary()
        self.format_hint.clear()
        self.preset_group.setTitle(self._tr("preset_group_title"))
        self.preset_title.setText(f"<b>{html.escape(title)}</b>")
        self.preset_body.setText(f"<p>{html.escape(body)}</p>")
        if invalid_video_name:
            self.summary_text.setHtml(self._render_summary_html(None))
            self.guidance_text.setHtml(
                f"<p>{html.escape(self._tr('invalid_video_file', name=invalid_video_name))}</p>"
            )
            return
        info = self._selected_video_info()
        self.summary_text.setHtml(self._render_summary_html(info))
        self.guidance_text.setHtml(self._render_guidance_html(info))

    def _apply_language(self) -> None:
        self.setWindowTitle(self._tr("window_title"))
        self.btn_add.setText(self._tr("add_files"))
        self.btn_remove.setText(self._tr("remove_selected"))
        self.btn_clear.setText(self._tr("clear"))
        self.output_label.setText(self._tr("output"))
        self.btn_output_change.setText(self._tr("change_output"))
        self.btn_output_open.setText(self._tr("open_output"))
        self.language_label.setText(self._tr("language"))
        self.btn_about.setText(self._tr("about"))
        self.engine_profile_label.setText(self._tr("engine_profile"))
        self.format_label.setText(self._tr("format"))
        self.quality_label.setText(self._tr("quality"))
        self.resolution_label.setText(self._tr("resolution"))
        self.resolution.setItemText(0, self._tr("keep_original"))
        if self.resolution.currentText() in self._all_translations("keep_original"):
            self.resolution.setCurrentText(self._tr("keep_original"))
        self.fps_label.setText(self._tr("fps"))
        self.keep_audio.setText(self._tr("keep_audio"))
        self.ogv_mode_label.setText(self._tr("ogv_mode"))
        self.frames_label.setText(self._tr("frames"))
        self.mode_label.setText(self._tr("mode"))
        self.atlas_resolution_label.setText(self._tr("resolution"))
        self.rec_group.setTitle(self._tr("rec_title"))
        self.btn_cancel.setText(self._tr("cancel"))
        self.tabs.setTabText(0, self._tr("tab_convert"))
        self.tabs.setTabText(1, self._tr("tab_atlas"))
        self._reload_ogv_mode_options(self.engine_profile.currentText(), self._ogv_mode_value())
        self._reload_atlas_mode_options(self._atlas_mode_value())
        self._reload_atlas_resolution_options(self._atlas_resolution_value())
        self._update_action_button()
        self._refresh_status_label()
        self._refresh_experience_panels()

    def on_language_changed(self):
        self._apply_language()
        self.refresh_selected_info()
        self.save_ui_settings()

    def on_engine_profile_changed(self):
        self._reload_ogv_mode_options(self.engine_profile.currentText())
        self._refresh_experience_panels()
        self.save_ui_settings()

    def _coerce_video_fps(self, value: str | float | int | None) -> float:
        try:
            fps = float(value) if value is not None else 30.0
        except (TypeError, ValueError):
            fps = 30.0
        return max(1.0, min(60.0, fps))

    def _selected_inputs(self) -> list[str]:
        selected = [x.text() for x in self.files.selectedItems()]
        if selected:
            return selected
        return [self.files.item(i).text() for i in range(self.files.count())]

    def _is_probable_video_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.VIDEO_EXTENSIONS

    def _cached_probe(self, src: str):
        cached = self._probe_cache.get(src)
        if cached is not None:
            return cached
        info = probe_video(str(self.ffprobe), src)
        self._probe_cache[src] = info
        return info

    def _set_busy(self, busy: bool):
        self.btn_action.setEnabled(not busy)
        self.files.setEnabled(not busy)
        self.btn_add.setEnabled(not busy)
        self.btn_remove.setEnabled(not busy)
        self.btn_clear.setEnabled(not busy)
        self.output.setEnabled(not busy)
        self.btn_output_change.setEnabled(not busy)
        self.btn_output_open.setEnabled(True)
        self.btn_about.setEnabled(not busy)
        self.language.setEnabled(not busy)
        self.tabs.setEnabled(not busy)
        self.format.setEnabled(not busy)
        self.quality.setEnabled(not busy)
        self.resolution.setEnabled(not busy)
        self.fps.setEnabled(not busy)
        self.engine_profile.setEnabled(not busy)
        self.keep_audio.setEnabled(not busy)
        self.ogv_mode.setEnabled(not busy and self.format.currentText().strip().lower() == "ogv")
        self.atlas_fps.setEnabled(not busy)
        self.atlas_mode.setEnabled(not busy)
        self.atlas_res.setEnabled(not busy)
        self.btn_cancel.setEnabled(busy)

    def _update_action_button(self) -> None:
        if self.tabs.currentIndex() == 0:
            self.btn_action.setText(self._tr("action_convert"))
        else:
            self.btn_action.setText(self._tr("action_atlas"))

    def _update_ogv_mode_state(self) -> None:
        is_ogv = self.format.currentText().strip().lower() == "ogv"
        self.ogv_mode_label.setEnabled(is_ogv)
        self.ogv_mode.setEnabled(is_ogv)

    def _reload_ogv_mode_options(self, engine_profile: str, selected: str | None = None) -> None:
        current = (selected if selected is not None else self._ogv_mode_value()).strip()
        options = list(ogv_modes_for_profile(engine_profile))
        self.ogv_mode.blockSignals(True)
        self.ogv_mode.clear()
        for option in options:
            self.ogv_mode.addItem(self._ogv_mode_label(option), option)
        idx = self.ogv_mode.findData(current)
        if idx < 0 and current:
            idx = self.ogv_mode.findText(current)
        if idx >= 0:
            self.ogv_mode.setCurrentIndex(idx)
        else:
            self.ogv_mode.setCurrentIndex(0)
        self.ogv_mode.blockSignals(False)

    def on_action(self):
        if self.tabs.currentIndex() == 0:
            self.on_convert()
        else:
            self.on_atlas()

    def _start_worker(self, fn):
        self._thread = QThread(self)
        self._cancel_event = Event()
        self._worker = Worker(fn, self._cancel_event)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._handle_worker_progress)
        self._worker.status.connect(self._handle_worker_status)
        self._worker.done.connect(self._on_worker_done)

        self._set_busy(True)
        self._reset_progress_bar(indeterminate=True)
        self._thread.start()

    def _add_files(self, files: list[str]) -> None:
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        added = 0
        rejected = 0
        for f in files:
            if not f or f in existing:
                continue
            p = Path(f)
            if not p.exists() or not p.is_file():
                continue
            if not self._is_probable_video_file(p):
                rejected += 1
                continue
            self.files.addItem(f)
            existing.add(f)
            added += 1

        if added == 0 and rejected > 0:
            self._set_status_key("no_valid_files_added")
        elif added > 0 and rejected > 0:
            self._set_status_key("added_rejected", added=added, rejected=rejected)
        elif added > 0:
            self._set_status_key("added_n_files", added=added)

        if self.files.count() > 0 and not self.files.selectedItems():
            self.files.setCurrentRow(0)
            self.refresh_selected_info()

    def refresh_selected_info(self) -> None:
        items = self.files.selectedItems()
        if not items:
            self._refresh_experience_panels()
            return

        src = items[0].text()
        try:
            info = self._cached_probe(src)
            if not info.is_valid:
                self._refresh_experience_panels(invalid_video_name=Path(src).name)
                return
            self._refresh_experience_panels()
        except Exception:
            self._refresh_experience_panels(invalid_video_name=Path(src).name)

    def on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, self._tr("select_videos"))
        self._add_files(files)

    def on_remove_selected(self):
        for item in self.files.selectedItems():
            self._probe_cache.pop(item.text(), None)
            self.files.takeItem(self.files.row(item))
        self.refresh_selected_info()

    def on_clear(self):
        self.files.clear()
        self._probe_cache.clear()
        self.refresh_selected_info()
        self._set_status_key("list_cleared")

    def on_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, self._tr("select_output_folder"), self.output.text())
        if folder:
            self.output.setText(folder)
            self._ensure_output_directory(notify=True)

    def on_open_output_dir(self):
        output = self._ensure_output_directory(notify=True)
        if output is None:
            return
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(output.resolve())))
        if not opened:
            QMessageBox.warning(self, self._tr("open_output_folder"), self._tr("open_output_folder_error"))

    def on_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self._tr("about"))
        dialog.resize(520, 260)

        layout = QVBoxLayout(dialog)
        title = QLabel(self._tr("window_title"))
        body = QLabel(self._tr("about_text", version=__version__))
        body.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
        buttons.accepted.connect(dialog.accept)

        layout.addWidget(title)
        layout.addWidget(body, 1)
        layout.addWidget(buttons)

        dialog.exec()

    def on_cancel(self):
        if self._cancel_event:
            self._cancel_event.set()
            self._set_status_key("cancelling")

    def on_convert(self):
        inputs = self._selected_inputs()
        if not inputs:
            QMessageBox.warning(self, self._tr("no_files_title"), self._tr("no_files_text"))
            return

        try:
            fps_val = float(self.fps.value())
        except ValueError as exc:
            QMessageBox.warning(self, self._tr("invalid_fps_title"), str(exc))
            return

        output = self._ensure_output_directory(notify=True)
        if output is None:
            return

        convert_cfg = {
            "engine_profile": self.engine_profile.currentText(),
            "format": self.format.currentText(),
            "quality": self.quality.currentText(),
            "resolution": self.resolution.currentText(),
            "fps": fps_val,
            "keep_audio": self.keep_audio.isChecked(),
            "ogv_mode": self._ogv_mode_value(),
        }

        def _run(cancel_event: Event, progress_cb, status_cb):
            total = len(inputs)
            for idx, src in enumerate(inputs, start=1):
                if cancel_event.is_set():
                    raise RuntimeError("conversion cancelled by user")
                source_name = Path(src).name
                status_cb({"key": "preparing_status", "kwargs": {"index": idx, "total": total, "name": source_name}})

                info = self._cached_probe(src)
                if self._is_heavy_video(info):
                    status_cb({"key": "heavy_video_status", "kwargs": {"name": source_name}})

                stem = Path(src).stem
                ext = {"ogv": ".ogv", "mp4": ".mp4", "webm": ".webm", "gif": ".gif"}[convert_cfg["format"]]
                dst = output / f"{stem}_converted{ext}"
                counter = 1
                while dst.exists():
                    dst = output / f"{stem}_converted_{counter}{ext}"
                    counter += 1

                status_cb({"key": "converting_status", "kwargs": {"index": idx, "total": total, "name": source_name}})

                def _per_file(p: int):
                    percent = int(((idx - 1) * 100 + p) / total)
                    progress_cb(percent)

                def _per_status(stage: str):
                    stage_to_key = {
                        "probe_input": "ffmpeg_probe_status",
                        "prepare_filters": "ffmpeg_prepare_filters_status",
                        "ffmpeg_launch": "ffmpeg_launch_status",
                        "ffmpeg_warmup": "ffmpeg_warmup_status",
                        "ffmpeg_encoding": "ffmpeg_encoding_status",
                    }
                    key = stage_to_key.get(stage)
                    if key:
                        status_cb({"key": key, "kwargs": {"name": source_name}})

                convert_video(
                    str(self.ffmpeg),
                    str(self.ffprobe),
                    src,
                    ConvertOptions(
                        output_file=str(dst),
                        engine_profile=convert_cfg["engine_profile"],
                        fmt=convert_cfg["format"],
                        quality=convert_cfg["quality"],
                        keep_audio=convert_cfg["keep_audio"],
                        fps=convert_cfg["fps"],
                        resolution=convert_cfg["resolution"],
                        ogv_mode=convert_cfg["ogv_mode"],
                    ),
                    on_progress=_per_file,
                    on_status=_per_status,
                    cancel_event=cancel_event,
                )

            progress_cb(100)

        self._start_worker(_run)

    def on_atlas(self):
        inputs = self._selected_inputs()
        if not inputs:
            QMessageBox.warning(self, self._tr("no_files_title"), self._tr("no_files_text"))
            return

        output = self._ensure_output_directory(notify=True)
        if output is None:
            return

        atlas_cfg = {
            "fps": self.atlas_fps.value(),
            "mode": self._atlas_mode_value(),
            "resolution": self._atlas_resolution_value(),
        }

        def _run(cancel_event: Event, progress_cb, status_cb):
            total = len(inputs)
            for idx, src in enumerate(inputs, start=1):
                if cancel_event.is_set():
                    raise RuntimeError("atlas generation cancelled by user")

                stem = Path(src).stem
                dst = output / f"{stem}_atlas.png"
                counter = 1
                while dst.exists():
                    dst = output / f"{stem}_atlas_{counter}.png"
                    counter += 1

                status_cb({"key": "atlas_status", "kwargs": {"index": idx, "total": total, "name": Path(src).name}})

                def _per_file(p: int):
                    percent = int(((idx - 1) * 100 + p) / total)
                    progress_cb(percent)

                result = generate_sprite_atlas(
                    str(self.ffmpeg),
                    str(self.ffprobe),
                    src,
                    str(dst),
                    fps=atlas_cfg["fps"],
                    mode=atlas_cfg["mode"],
                    atlas_resolution=atlas_cfg["resolution"],
                    cancel_event=cancel_event,
                    on_progress=_per_file,
                )

            progress_cb(100)

        self._start_worker(_run)


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(_app_icon())
    _apply_default_theme(app)
    try:
        win = MainWindow()
    except FFmpegNotFoundError as exc:
        lang = load_settings().selected_language
        title = ui_text(lang, "ffmpeg_not_found")
        QMessageBox.critical(None, title, str(exc))
        raise SystemExit(2)

    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
