# Godot Video Converter

Desktop app for converting video and audio into game-ready formats, especially `ogv` for Godot and others engines, plus sprite atlas generation for 2D workflows.

This project is a Python rewrite of the original .NET tool I made some time ago.

## Download

[![Windows and Linux on itch.io](https://img.shields.io/badge/Windows_%26_Linux-itch.io-FA5C5C?style=for-the-badge&logo=itchdotio&logoColor=white)](https://lextrack.itch.io/godot-video-converter)

## Features

- Convert videos to `ogv`, `mp4`, `webm`, and `gif`
- Convert audio to `ogg`, `mp3`, `aac`, and `wav`
- Extract audio from video files
- Use Godot-focused OGV presets
- Use Love2D-focused OGV presets
- Generate PNG sprite atlases from video
- Batch process files from a GUI
- Show export summaries and recommendations

## Main Workflows

### Video Conversion

- `ogv` is the main target for Godot playback
- `mp4`, `webm`, and `gif` are also available
- Quality, FPS, resolution, audio, and OGV mode can be adjusted from the GUI.
- Each engine has its own OGV modes.
- Some `.mp4` files downloaded directly from YouTube Music may include unusual embedded artwork or metadata. On Windows, these files can trigger `.ogv` preview or file-lock issues in Explorer even when the converted file itself is valid and plays correctly in Godot.

### Audio Conversion

- Convert audio files to `ogg`, `mp3`, `aac`, or `wav`
- Extract audio from selected video files
- For Godot, use `ogg` for music/loops and `wav` for short SFX

### Atlas Generation

- Export PNG atlases from video clips
- Layout modes: `grid`, `horizontal`, `vertical`
- Uses `ffmpeg` for frame sampling and atlas generation

## Requirements

- Python `3.11+`
- `ffmpeg`
- `ffprobe`

On Windows, the app can use:

- `bin/ffmpeg.exe` and `bin/ffprobe.exe`
- `GVC_FFMPEG_DIR`
- `ffmpeg` and `ffprobe` from `PATH`

On Linux, `ffmpeg` and `ffprobe` should be available in `PATH`.

## Development Environment

The project metadata in `pyproject.toml` is the source of truth for dependencies.

- Use `pip install -e .` for regular development.

### Windows

1. Install Python `3.11+`.
2. Clone or download this repository.
3. Create a virtual environment:

```powershell
python -m venv .venv
```

4. Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

5. Install the app in editable mode:

```powershell
pip install -e .
```

6. Make sure FFmpeg (7.1.1 recommended version) is available using ONE of these options:

- Copy `ffmpeg.exe` and `ffprobe.exe` into `bin/`
- Set `GVC_FFMPEG_DIR` to the folder that contains both binaries
- Add FFmpeg to `PATH`

7. Run the app:

```powershell
gvc-gui
```

### Linux

1. Install Python `3.11+`.
2. Install FFmpeg with your package manager.
3. Clone or download this repository.
4. Create a virtual environment:

```bash
python3 -m venv .venv
```

5. Activate it:

```bash
source .venv/bin/activate
```

If you use `fish`, activate it with:

```fish
source .venv/bin/activate.fish
```

6. Install the app in editable mode:

```bash
python -m pip install -e .
```

7. Verify FFmpeg:

```bash
ffmpeg -version
ffprobe -version
```

8. Run the app:

```bash
gvc-gui
```

If the console command is not available for any reason, you can also run:

```bash
python -m gvc
```

### Linux Package Examples

```bash
# Arch / CachyOS
sudo pacman -S ffmpeg python

# Debian / Ubuntu
sudo apt update
sudo apt install ffmpeg python3 python3-venv python3-pip

# Fedora
sudo dnf install ffmpeg python3 python3-pip

# openSUSE
sudo zypper install ffmpeg python3 python3-pip
```

## Running the GUI

With the virtual environment active on Windows or Linux:

```bash
gvc-gui
```

## Portable Build

### Linux build options

Linux releases can be built in two ways. Neither package includes FFmpeg, so end
users need their distribution's `ffmpeg` package, with both `ffmpeg` and
`ffprobe` available in `PATH`.

| Build | Command | Output | Best for |
| --- | --- | --- | --- |
| PyInstaller folder | `bash scripts/build_linux.sh` | `dist/gvc/` | Users who prefer a conventional executable folder or a ZIP download. |
| AppImage | `bash scripts/build_appimage.sh` | `dist/godot-video-converter-<version>-<architecture>.AppImage` | A single portable download for most Linux desktop distributions. |

### Linux: PyInstaller folder

On a Linux machine, run:

```bash
bash scripts/build_linux.sh
```

The script installs the required build dependencies and runs `PyInstaller` with `gvc.spec`.
The result is the `dist/gvc/` directory. Distribute that whole directory (for
example, as a `.zip`); users run `gvc` inside it.

### Linux: AppImage

On a Linux machine, run:

```bash
bash scripts/build_appimage.sh
```

The build creates `dist/godot-video-converter-<version>-<architecture>.AppImage`.
It downloads the pinned and SHA-256-verified `appimagetool` release into
`.appimage/tools/` on the first run; alternatively, set `APPIMAGETOOL` to a local,
trusted executable. The AppImage bundles Python, PySide6, and
the application, but deliberately does **not** bundle FFmpeg. Users must install
their distribution's `ffmpeg` package so both `ffmpeg` and `ffprobe` are in `PATH`.

To run a released AppImage:

```bash
chmod +x godot-video-converter-*.AppImage
./godot-video-converter-*.AppImage
```

## Tests

The automated unit tests do not need FFmpeg or a graphical session:

```bash
python -m unittest discover -s tests -v
```

### Windows

Copy `ffmpeg.exe` and `ffprobe.exe` into `bin/`, then run:

```powershell
./scripts/build_windows.ps1
```

The script installs the required build dependencies and runs `PyInstaller` with `gvc.spec`.
Output is generated in `dist/gvc/`.
Run `dist/gvc/gvc.exe`.
