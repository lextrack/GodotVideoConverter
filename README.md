# Godot Video Converter

Desktop app for converting videos into game-ready formats, especially `ogv` for Godot, plus sprite atlas generation for 2D workflows.

This project is a Python rewrite of the original .NET tool I made some time ago.

## Download

[![Windows and Linux on itch.io](https://img.shields.io/badge/Windows_%26_Linux-itch.io-FA5C5C?style=for-the-badge&logo=itchdotio&logoColor=white)](https://lextrack.itch.io/godot-video-converter)

## Features

- Convert videos to `ogv`, `mp4`, `webm`, and `gif`
- Use Godot-focused OGV presets
- Use Love2D-focused OGV presets
- Generate PNG sprite atlases from video
- Batch process files from a GUI
- Analyze source video before export

## Main Workflows

### Video Conversion

- `ogv` is the main target for Godot playback
- `mp4`, `webm`, and `gif` are also available
- Quality, FPS, resolution, audio, and OGV mode can be adjusted from the GUI

Godot OGV modes:

- `Official Godot`
- `Seek Friendly`
- `Ideal Loop`
- `Mobile Optimized`
- `High Compression`

Love2D OGV modes:

- `Love2D Compatibility`
- `Seek Friendly`
- `Ideal Loop`
- `Lightweight`

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

6. Make sure FFmpeg (7.1.1 recomended version) is available using ONE of these options:

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

### Linux

Make sure `ffmpeg` and `ffprobe` are available in `PATH`, then run:

```bash
bash scripts/build_linux.sh
```

The script installs the required build dependencies and runs `PyInstaller` with `gvc.spec`.
Output is generated in `dist/gvc/`.

### Windows

Copy `ffmpeg.exe` and `ffprobe.exe` into `bin/`, then run:

```powershell
./scripts/build_windows.ps1
```

The script installs the required build dependencies and runs `PyInstaller` with `gvc.spec`.
Output is generated in `dist/gvc/`.
Run `dist/gvc/gvc.exe`.
