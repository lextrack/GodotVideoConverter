from __future__ import annotations

import html
import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QThread, QTimer, Signal, QUrl
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPalette,
)
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QLabel, QMainWindow, QMessageBox, QVBoxLayout

from gvc.batch import AtlasBatchConfig, BatchPaths, ConvertBatchConfig, ProbeCache, convert_batch, generate_atlas_batch
from gvc.convert import ENGINE_PROFILES, ogv_modes_for_profile, validate_resolution
from gvc.experience import ExperienceContext, guidance_html, preset_summary, summary_html
from gvc.ffmpeg_paths import FFmpegNotFoundError, resolve_ffmpeg_and_ffprobe
from gvc import __version__
from gvc.i18n import LANGUAGE_LABELS, language_label_to_code, translate_runtime_error, ui_text
from gvc.probe import probe_video
from gvc.settings import load_settings
from gvc.ui_panels import build_main_window_ui
from gvc.ui_state import apply_saved_settings, save_window_settings


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

        build_main_window_ui(self, LANGUAGE_LABELS, ENGINE_PROFILES)

        self.btn_add.clicked.connect(self.on_add_files)
        self.btn_remove.clicked.connect(self.on_remove_selected)
        self.btn_clear.clicked.connect(self.on_clear)
        self.files_delete_shortcut.activated.connect(self.on_remove_selected)
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

        apply_saved_settings(self)
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

    def save_ui_settings(self, *_args) -> None:
        save_window_settings(self)

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

    def _experience_context(self) -> ExperienceContext:
        return ExperienceContext(
            engine_profile=self.engine_profile.currentText(),
            fmt=self.format.currentText(),
            quality=self.quality.currentText(),
            resolution=self.resolution.currentText().strip(),
            fps=float(self.fps.value()),
            keep_audio=self.keep_audio.isChecked(),
            ogv_mode=self._ogv_mode_value(),
            output_folder=self.output.text().strip() or "output",
            source_path=self._selected_primary_path(),
            language_code=self._lang_code(),
            keep_original_labels=frozenset(self._all_translations("keep_original")),
        )

    def _refresh_experience_panels(self, *_args, invalid_video_name: str | None = None) -> None:
        ctx = self._experience_context()
        title, body = preset_summary(ctx, self._tr)
        self.format_hint.clear()
        self.preset_group.setTitle(self._tr("preset_group_title"))
        self.preset_title.setText(f"<b>{html.escape(title)}</b>")
        self.preset_body.setText(f"<p>{html.escape(body)}</p>")
        if invalid_video_name:
            self.summary_text.setHtml(summary_html(ctx, None, self._tr))
            self.guidance_text.setHtml(
                f"<p>{html.escape(self._tr('invalid_video_file', name=invalid_video_name))}</p>"
            )
            return
        info = self._selected_video_info()
        self.summary_text.setHtml(summary_html(ctx, info, self._tr))
        self.guidance_text.setHtml(guidance_html(ctx, info, self._tr))

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
        self.atlas_resolution_label.setText(self._tr("atlas_frame_size"))
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

    def _normalized_resolution_value(self) -> str:
        current = self.resolution.currentText().strip()
        if not current or current in self._all_translations("keep_original"):
            return "Keep original"
        return current

    def _validate_resolution_from_ui(self) -> str | None:
        resolution = self._normalized_resolution_value()
        try:
            validate_resolution(resolution)
        except ValueError:
            QMessageBox.warning(
                self,
                self._tr("invalid_resolution_title"),
                self._tr("invalid_resolution_text", value=self.resolution.currentText().strip()),
            )
            return None
        return resolution

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
        resolution = self._validate_resolution_from_ui()
        if resolution is None:
            return

        paths = BatchPaths(ffmpeg=str(self.ffmpeg), ffprobe=str(self.ffprobe), output_dir=output)
        config = ConvertBatchConfig(
            engine_profile=self.engine_profile.currentText(),
            fmt=self.format.currentText(),
            quality=self.quality.currentText(),
            resolution=resolution,
            fps=fps_val,
            keep_audio=self.keep_audio.isChecked(),
            ogv_mode=self._ogv_mode_value(),
        )
        probe_cache = ProbeCache(
            str(self.ffprobe),
            {src: self._probe_cache[src] for src in inputs if src in self._probe_cache},
        )

        def _run(cancel_event: Event, progress_cb, status_cb):
            convert_batch(
                inputs,
                paths,
                config,
                probe_cache=probe_cache,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
                status_cb=status_cb,
            )

        self._start_worker(_run)

    def on_atlas(self):
        inputs = self._selected_inputs()
        if not inputs:
            QMessageBox.warning(self, self._tr("no_files_title"), self._tr("no_files_text"))
            return

        output = self._ensure_output_directory(notify=True)
        if output is None:
            return

        paths = BatchPaths(ffmpeg=str(self.ffmpeg), ffprobe=str(self.ffprobe), output_dir=output)
        config = AtlasBatchConfig(
            fps=self.atlas_fps.value(),
            mode=self._atlas_mode_value(),
            resolution=self._atlas_resolution_value(),
        )

        def _run(cancel_event: Event, progress_cb, status_cb):
            generate_atlas_batch(
                inputs,
                paths,
                config,
                cancel_event=cancel_event,
                progress_cb=progress_cb,
                status_cb=status_cb,
            )

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
