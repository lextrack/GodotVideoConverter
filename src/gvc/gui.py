from __future__ import annotations

import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import QThread, QTimer, QUrl
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QPalette,
)
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

from gvc.convert import ENGINE_PROFILES, validate_resolution
from gvc.dialogs import (
    confirm_cancel_running,
    show_about,
    show_ffmpeg_not_found,
    show_invalid_resolution,
    show_open_output_failed,
    show_output_error,
)
from gvc.ffmpeg_paths import FFmpegNotFoundError, resolve_ffmpeg_and_ffprobe
from gvc import __version__
from gvc.gui_experience import (
    on_atlas_start_changed,
    refresh_experience_panels,
    sync_atlas_range_with_selected_video,
)
from gvc.gui_operations import start_atlas, start_audio, start_convert
from gvc.gui_selection import (
    add_files,
    cached_probe,
    clear_all,
    inputs_for_current_operation,
    is_audio_only_source,
    refresh_selected_info,
    remove_selected,
    selected_primary,
    selected_source_is_video,
)
from gvc.gui_state_controller import (
    reload_ogv_mode_options,
    set_busy,
    set_info_panel_visible,
    update_action_button,
    update_audio_bitrate_state,
    update_info_toggle_button,
    update_ogv_mode_state,
)
from gvc.i18n import LANGUAGE_LABELS, language_label_to_code, translate_runtime_error, ui_text
from gvc.qt_worker import Worker
from gvc.settings import load_settings
from gvc.ui_language import apply_language
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
    app.setStyleSheet(
        """
        QWidget {
            font-family: "Inter", "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", "WenQuanYi Micro Hei", sans-serif;
            font-size: 10.5pt;
        }
        QLabel[gvcRole="fieldLabel"] {
            color: #9ecbff;
            font-weight: 600;
        }
        QLabel[gvcRole="fieldLabel"]:disabled {
            color: #687386;
        }
        QLabel[gvcRole="fieldHint"] {
            color: #b8c0cc;
        }
        QLabel[gvcRole="fieldHint"]:disabled {
            color: #687386;
        }
        """
    )


class MainWindow(QMainWindow):
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
        self._info_panel_visible = True
        self._atlas_range_source: str | None = None
        self._output_validation_timer = QTimer(self)
        self._output_validation_timer.setInterval(4000)
        self._output_validation_timer.timeout.connect(self._ensure_output_directory_silent)
        self._progress_clear_timer = QTimer(self)
        self._progress_clear_timer.setSingleShot(True)
        self._progress_clear_timer.setInterval(5000)
        self._progress_clear_timer.timeout.connect(self._reset_progress_bar)

        build_main_window_ui(self, LANGUAGE_LABELS, ENGINE_PROFILES)

        self.btn_add.clicked.connect(self.on_add_files)
        self.btn_remove.clicked.connect(self.on_remove_selected)
        self.btn_clear.clicked.connect(self.on_clear)
        self.btn_toggle_info.clicked.connect(self.on_toggle_info_panel)
        self.files_delete_shortcut.activated.connect(self.on_remove_selected)
        self.btn_output_change.clicked.connect(self.on_output_dir)
        self.btn_output_open.clicked.connect(self.on_open_output_dir)
        self.btn_about.clicked.connect(self.on_about)
        self.btn_action.clicked.connect(self.on_action)
        self.btn_cancel.clicked.connect(self.on_cancel)
        self.tabs.currentChanged.connect(self._update_action_button)
        self.tabs.currentChanged.connect(lambda _index: self.refresh_selected_info())
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
        self.audio_format.currentTextChanged.connect(self.save_ui_settings)
        self.audio_format.currentTextChanged.connect(self._update_audio_bitrate_state)
        self.audio_format.currentTextChanged.connect(self._refresh_experience_panels)
        self.audio_bitrate.currentTextChanged.connect(self.save_ui_settings)
        self.audio_bitrate.currentTextChanged.connect(self._refresh_experience_panels)
        self.audio_sample_rate.currentTextChanged.connect(self.save_ui_settings)
        self.audio_sample_rate.currentTextChanged.connect(self._refresh_experience_panels)
        self.audio_channels.currentTextChanged.connect(self.save_ui_settings)
        self.audio_channels.currentTextChanged.connect(self._refresh_experience_panels)
        self.atlas_fps.valueChanged.connect(self.save_ui_settings)
        self.atlas_fps.valueChanged.connect(self._refresh_experience_panels)
        self.atlas_mode.currentTextChanged.connect(self.save_ui_settings)
        self.atlas_mode.currentTextChanged.connect(self._refresh_experience_panels)
        self.atlas_res.currentTextChanged.connect(self.save_ui_settings)
        self.atlas_res.currentTextChanged.connect(self._refresh_experience_panels)
        self.atlas_start.valueChanged.connect(self._on_atlas_start_changed)
        self.atlas_start.valueChanged.connect(self._refresh_experience_panels)
        self.atlas_duration.valueChanged.connect(self._refresh_experience_panels)

        apply_saved_settings(self)
        self._ensure_output_directory_silent()
        self._apply_language()
        self._update_action_button()
        self._update_ogv_mode_state()
        self._update_audio_bitrate_state()
        self._output_validation_timer.start()

    def _on_worker_done(self, ok: bool) -> None:
        self._set_busy(False)
        if ok and not (self._cancel_event and self._cancel_event.is_set()):
            self._set_status_key("done")
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            self._progress_clear_timer.start()
        elif self._cancel_event and self._cancel_event.is_set():
            self._set_status_key("cancelled")
            self._reset_progress_bar()
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
                show_output_error(self, self._tr, str(exc))
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
        self._progress_clear_timer.stop()
        self._progress_started = False
        self._set_progress_error_state(False)
        if indeterminate:
            self.progress.setRange(0, 0)
            self.progress.setValue(0)
            return
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def _freeze_progress_bar_on_error(self) -> None:
        self._progress_clear_timer.stop()
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
            if not confirm_cancel_running(self, self._tr):
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

    def _quality_value(self) -> str:
        data = self.quality.currentData()
        if isinstance(data, str) and data.strip():
            return data
        return self.quality.currentText().strip().lower()

    def _audio_format_value(self) -> str:
        return self._combo_data_value(self.audio_format, "ogg")

    def _audio_bitrate_value(self) -> str:
        return self._combo_data_value(self.audio_bitrate, "160k")

    def _audio_sample_rate_value(self) -> str:
        return self._combo_data_value(self.audio_sample_rate, "44100")

    def _audio_channels_value(self) -> str:
        return self._combo_data_value(self.audio_channels, "stereo")

    def _combo_data_value(self, combo, fallback: str) -> str:
        data = combo.currentData()
        if isinstance(data, str) and data.strip():
            return data
        text = combo.currentText().strip()
        return text or fallback

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
        return selected_primary(self)

    def _is_audio_only_source(self, src: str) -> bool:
        return is_audio_only_source(self, src)

    def _selected_source_is_video(self) -> bool:
        return selected_source_is_video(self)

    def _on_atlas_start_changed(self, _value: float) -> None:
        on_atlas_start_changed(self)

    def _refresh_experience_panels(self, *_args, invalid_video_name: str | None = None) -> None:
        refresh_experience_panels(self, invalid_video_name=invalid_video_name)

    def _apply_language(self) -> None:
        apply_language(self)

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
            show_invalid_resolution(self, self._tr, self.resolution.currentText().strip())
            return None
        return resolution

    def _inputs_for_current_operation(self) -> list[str] | None:
        return inputs_for_current_operation(self)

    def _cached_probe(self, src: str):
        return cached_probe(self, src)

    def _set_busy(self, busy: bool):
        set_busy(self, busy)

    def _update_action_button(self) -> None:
        update_action_button(self)

    def _set_info_panel_visible(self, visible: bool, *, save: bool = True) -> None:
        set_info_panel_visible(self, visible, save=save)

    def _update_info_toggle_button(self) -> None:
        update_info_toggle_button(self)

    def _update_ogv_mode_state(self) -> None:
        update_ogv_mode_state(self)

    def _update_audio_bitrate_state(self) -> None:
        update_audio_bitrate_state(self)

    def _reload_ogv_mode_options(self, engine_profile: str, selected: str | None = None) -> None:
        reload_ogv_mode_options(self, engine_profile, selected=selected)

    def on_action(self):
        if self.tabs.currentIndex() == 0:
            self.on_convert()
        elif self.tabs.currentIndex() == 1:
            self.on_audio()
        else:
            self.on_atlas()

    def _start_worker(self, fn):
        self._progress_clear_timer.stop()
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
        add_files(self, files)

    def refresh_selected_info(self) -> None:
        refresh_selected_info(self)

    def on_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, self._tr("select_videos"))
        self._add_files(files)

    def on_remove_selected(self):
        remove_selected(self)

    def on_clear(self):
        clear_all(self)

    def on_toggle_info_panel(self, _checked: bool = False):
        self._set_info_panel_visible(not self._info_panel_visible)

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
            show_open_output_failed(self, self._tr)

    def on_about(self):
        show_about(self, self._tr, __version__)

    def on_cancel(self):
        if self._cancel_event:
            self._cancel_event.set()
            self._set_status_key("cancelling")

    def on_convert(self):
        start_convert(self)

    def on_audio(self):
        start_audio(self)

    def on_atlas(self):
        start_atlas(self)


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(_app_icon())
    _apply_default_theme(app)
    try:
        win = MainWindow()
    except FFmpegNotFoundError as exc:
        lang = load_settings().selected_language
        show_ffmpeg_not_found(lang, str(exc))
        raise SystemExit(2)

    win.show()
    raise SystemExit(app.exec())


if __name__ == "__main__":
    main()
