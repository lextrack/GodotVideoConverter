from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


RESOLUTION_PRESETS = (
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
)

QUALITY_OPTIONS = (
    "ultra",
    "high",
    "balanced",
    "optimized",
    "tiny",
)

AUDIO_FORMAT_OPTIONS = ("ogg", "mp3", "aac", "wav")
AUDIO_BITRATE_OPTIONS = ("96k", "128k", "160k", "192k", "256k", "320k")
AUDIO_SAMPLE_RATE_OPTIONS = ("keep", "44100", "48000")
AUDIO_CHANNEL_OPTIONS = ("keep", "mono", "stereo")


def build_main_window_ui(win, language_labels: tuple[str, ...], engine_profiles: tuple[str, ...]) -> None:
    root = QWidget()
    win.setCentralWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(8)

    win.content_splitter = QSplitter(Qt.Orientation.Horizontal)
    win.content_splitter.setChildrenCollapsible(False)
    win.content_splitter.setHandleWidth(14)
    layout.addWidget(win.content_splitter, 1)

    left_panel = QWidget()
    left = QVBoxLayout(left_panel)
    left.setContentsMargins(0, 0, 0, 0)
    left.setSpacing(8)
    win.content_splitter.addWidget(left_panel)

    _build_files_row(win, left)
    _build_output_row(win, left, language_labels)
    _build_tabs(win, left, engine_profiles)
    _build_actions_row(win, left)
    _build_info_panel(win)

    win.progress = QProgressBar()
    win.status = QLabel("Ready")
    layout.addWidget(win.progress)
    layout.addWidget(win.status)


def _build_files_row(win, left: QVBoxLayout) -> None:
    files_row = QHBoxLayout()
    files_row.setSpacing(8)
    win.files = QListWidget()
    win.files.setSelectionMode(QListWidget.ExtendedSelection)
    win.files_delete_shortcut = QShortcut(QKeySequence.StandardKey.Delete, win.files)
    files_btns = QVBoxLayout()
    files_btns.setSpacing(8)
    win.btn_add = QPushButton("Add Files")
    win.btn_remove = QPushButton("Remove Selected")
    win.btn_clear = QPushButton("Clear")
    win.btn_add.setMinimumWidth(140)
    win.btn_remove.setMinimumWidth(140)
    win.btn_clear.setMinimumWidth(140)
    files_btns.addWidget(win.btn_add)
    files_btns.addWidget(win.btn_remove)
    files_btns.addWidget(win.btn_clear)
    files_btns.addStretch()
    files_row.addWidget(win.files, 1)
    files_row.addLayout(files_btns)
    left.addLayout(files_row)


def _build_output_row(win, left: QVBoxLayout, language_labels: tuple[str, ...]) -> None:
    out_row = QHBoxLayout()
    out_row.setSpacing(8)
    win.output = QLineEdit(str(Path.cwd() / "output"))
    win.btn_output_change = QPushButton("Change Output")
    win.btn_output_open = QPushButton("Open Output")
    win.btn_about = QPushButton("About")
    win.language = QComboBox()
    win.language.addItems(list(language_labels))
    win.language.setMinimumWidth(120)
    win.output_label = QLabel("Output:")
    win.language_label = QLabel("Language:")
    out_row.addWidget(win.output_label)
    out_row.addWidget(win.output, 1)
    out_row.addWidget(win.btn_output_change)
    out_row.addWidget(win.btn_output_open)
    out_row.addWidget(win.language_label)
    out_row.addWidget(win.language)
    out_row.addWidget(win.btn_about)
    left.addLayout(out_row)


def _build_tabs(win, left: QVBoxLayout, engine_profiles: tuple[str, ...]) -> None:
    win.tabs = QTabWidget()
    left.addWidget(win.tabs)

    convert_tab = QWidget()
    convert_layout = QVBoxLayout(convert_tab)
    _build_convert_controls(win, convert_layout, engine_profiles)

    audio_tab = QWidget()
    audio_layout = QVBoxLayout(audio_tab)
    _build_audio_controls(win, audio_layout)

    atlas_tab = QWidget()
    atlas_layout = QVBoxLayout(atlas_tab)
    _build_atlas_controls(win, atlas_layout)

    win.tabs.addTab(convert_tab, "Convert Video")
    win.tabs.addTab(audio_tab, "Convert Audio")
    win.tabs.addTab(atlas_tab, "Generate Atlas")


def _build_convert_controls(win, convert_layout: QVBoxLayout, engine_profiles: tuple[str, ...]) -> None:
    row1 = QGridLayout()
    row1.setHorizontalSpacing(10)
    row1.setVerticalSpacing(10)
    win.format = QComboBox()
    win.format.addItems(["ogv", "mp4", "webm", "gif"])
    win.format.setMinimumWidth(130)
    win.quality = QComboBox()
    for quality in QUALITY_OPTIONS:
        win.quality.addItem(quality, quality)
    win.quality.setMinimumWidth(130)
    win.resolution = QComboBox()
    win.resolution.setEditable(True)
    win.resolution.setMinimumWidth(170)
    win.resolution.addItems(list(RESOLUTION_PRESETS))
    win.resolution.setCurrentText("Keep original")
    win.fps = QDoubleSpinBox()
    win.fps.setRange(1.0, 60.0)
    win.fps.setDecimals(2)
    win.fps.setSingleStep(1.0)
    win.fps.setValue(30.0)
    win.fps.setMinimumWidth(95)
    win.format_label = QLabel("Format")
    win.quality_label = QLabel("Quality")
    win.resolution_label = QLabel("Resolution")
    win.fps_label = QLabel("FPS")
    row1.addWidget(win.format_label, 0, 0)
    row1.addWidget(win.format, 0, 1)
    row1.addWidget(win.quality_label, 0, 2)
    row1.addWidget(win.quality, 0, 3)
    row1.addWidget(win.resolution_label, 0, 4)
    row1.addWidget(win.resolution, 0, 5)
    row1.addWidget(win.fps_label, 0, 6)
    row1.addWidget(win.fps, 0, 7)
    row1.setColumnStretch(1, 1)
    row1.setColumnStretch(3, 1)
    row1.setColumnStretch(5, 1)
    convert_layout.addLayout(row1)

    win.format_hint = QLabel()
    win.format_hint.setWordWrap(True)
    win.format_hint.setTextFormat(Qt.TextFormat.RichText)
    convert_layout.addWidget(win.format_hint)

    row2 = QGridLayout()
    row2.setHorizontalSpacing(10)
    row2.setVerticalSpacing(10)
    win.engine_profile_label = QLabel("Engine Profile")
    win.engine_profile = QComboBox()
    win.engine_profile.addItems(list(engine_profiles))
    win.engine_profile.setMinimumWidth(150)
    win.keep_audio = QCheckBox("Keep audio")
    win.ogv_mode_label = QLabel("OGV mode")
    win.ogv_mode = QComboBox()
    win.ogv_mode.setMinimumWidth(240)
    win._reload_ogv_mode_options("Godot")
    row2.addWidget(win.engine_profile_label, 0, 0)
    row2.addWidget(win.engine_profile, 0, 1)
    row2.addWidget(win.keep_audio, 0, 2)
    row2.addWidget(win.ogv_mode_label, 0, 3)
    row2.addWidget(win.ogv_mode, 0, 4, 1, 3)
    row2.setColumnStretch(4, 1)
    convert_layout.addLayout(row2)

    win.preset_group = QGroupBox()
    preset_layout = QVBoxLayout(win.preset_group)
    win.preset_title = QLabel()
    win.preset_title.setWordWrap(True)
    win.preset_body = QLabel()
    win.preset_body.setWordWrap(True)
    win.preset_body.setTextFormat(Qt.TextFormat.RichText)
    preset_layout.addWidget(win.preset_title)
    preset_layout.addWidget(win.preset_body)
    convert_layout.addWidget(win.preset_group)


def _build_audio_controls(win, audio_layout: QVBoxLayout) -> None:
    row = QGridLayout()
    row.setHorizontalSpacing(10)
    row.setVerticalSpacing(10)

    win.audio_format_label = QLabel("Format")
    win.audio_format = QComboBox()
    for fmt in AUDIO_FORMAT_OPTIONS:
        win.audio_format.addItem(fmt, fmt)
    win.audio_format.setMinimumWidth(130)

    win.audio_bitrate_label = QLabel("Bitrate")
    win.audio_bitrate = QComboBox()
    for bitrate in AUDIO_BITRATE_OPTIONS:
        win.audio_bitrate.addItem(bitrate, bitrate)
    win.audio_bitrate.setCurrentText("160k")
    win.audio_bitrate.setMinimumWidth(130)

    win.audio_sample_rate_label = QLabel("Sample rate")
    win.audio_sample_rate = QComboBox()
    for sample_rate in AUDIO_SAMPLE_RATE_OPTIONS:
        win.audio_sample_rate.addItem(sample_rate, sample_rate)
    win.audio_sample_rate.setCurrentText("44100")
    win.audio_sample_rate.setMinimumWidth(150)

    win.audio_channels_label = QLabel("Channels")
    win.audio_channels = QComboBox()
    for channels in AUDIO_CHANNEL_OPTIONS:
        win.audio_channels.addItem(channels, channels)
    win.audio_channels.setCurrentText("stereo")
    win.audio_channels.setMinimumWidth(130)

    row.addWidget(win.audio_format_label, 0, 0)
    row.addWidget(win.audio_format, 0, 1)
    row.addWidget(win.audio_bitrate_label, 0, 2)
    row.addWidget(win.audio_bitrate, 0, 3)
    row.addWidget(win.audio_sample_rate_label, 0, 4)
    row.addWidget(win.audio_sample_rate, 0, 5)
    row.addWidget(win.audio_channels_label, 0, 6)
    row.addWidget(win.audio_channels, 0, 7)
    row.setColumnStretch(1, 1)
    row.setColumnStretch(3, 1)
    row.setColumnStretch(5, 1)
    row.setColumnStretch(7, 1)
    audio_layout.addLayout(row)

    win.audio_guidance_group = QGroupBox()
    guidance_layout = QVBoxLayout(win.audio_guidance_group)
    win.audio_guidance_title = QLabel()
    win.audio_guidance_title.setWordWrap(True)
    win.audio_guidance_body = QLabel()
    win.audio_guidance_body.setWordWrap(True)
    win.audio_video_source_note = QLabel()
    win.audio_video_source_note.setWordWrap(True)
    win.audio_video_source_note.setTextFormat(Qt.TextFormat.RichText)
    win.audio_video_source_note.setVisible(False)
    guidance_layout.addWidget(win.audio_guidance_title)
    guidance_layout.addWidget(win.audio_guidance_body)
    guidance_layout.addWidget(win.audio_video_source_note)
    audio_layout.addWidget(win.audio_guidance_group)
    audio_layout.addStretch()


def _build_atlas_controls(win, atlas_layout: QVBoxLayout) -> None:
    arow1 = QHBoxLayout()
    win.atlas_fps = QSpinBox()
    win.atlas_fps.setRange(1, 30)
    win.atlas_fps.setValue(5)
    win.atlas_mode = QComboBox()
    win.atlas_res = QComboBox()
    win.frames_label = QLabel("Frames")
    win.mode_label = QLabel("Mode")
    win.atlas_resolution_label = QLabel("Resolution")
    arow1.addWidget(win.frames_label)
    arow1.addWidget(win.atlas_fps)
    arow1.addWidget(win.mode_label)
    arow1.addWidget(win.atlas_mode)
    arow1.addWidget(win.atlas_resolution_label)
    arow1.addWidget(win.atlas_res)
    arow1.addStretch()
    atlas_layout.addLayout(arow1)


def _build_actions_row(win, left: QVBoxLayout) -> None:
    actions_row = QHBoxLayout()
    win.btn_action = QPushButton("Convert Video")
    win.btn_cancel = QPushButton("Cancel")
    win.btn_cancel.setEnabled(False)
    actions_row.addWidget(win.btn_action)
    actions_row.addWidget(win.btn_cancel)
    actions_row.addStretch()
    left.addLayout(actions_row)


def _build_info_panel(win) -> None:
    right_panel = QWidget()
    right = QVBoxLayout(right_panel)
    right.setContentsMargins(0, 0, 0, 0)
    right.setSpacing(8)
    win.content_splitter.addWidget(right_panel)
    win.content_splitter.setStretchFactor(0, 2)
    win.content_splitter.setStretchFactor(1, 3)
    win.content_splitter.setSizes([540, 940])

    win.rec_group = QGroupBox("Godot Recommendations")
    rec_group_layout = QVBoxLayout(win.rec_group)
    win.summary_text = QTextEdit()
    win.summary_text.setReadOnly(True)
    win.summary_text.setMinimumHeight(320)
    win.summary_text.setAcceptRichText(True)
    win.guidance_text = QTextEdit()
    win.guidance_text.setReadOnly(True)
    win.guidance_text.setMinimumHeight(290)
    win.guidance_text.setAcceptRichText(True)
    rec_group_layout.addWidget(win.summary_text)
    rec_group_layout.addWidget(win.guidance_text, 1)
    right.addWidget(win.rec_group, 1)
