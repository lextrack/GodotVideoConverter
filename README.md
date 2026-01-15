# Godot Video Converter

A specialized video conversion tool for Godot Engine developers.

## Purpose

Convert videos to Godot-compatible formats (especially OGV) with:

* Native Godot support without external plugins
* Game-oriented optimizations
* Batch processing capabilities
* Sprite atlas generation from videos

## Key Features

### Supported Formats

| Format                | Codecs        | Primary Purpose              | Godot Support                   | Recommended Usage   |
| --------------------- | ------------- | ---------------------------- | ------------------------------- | ------------------- |
| **OGV** (Recommended) | Theora/Vorbis | Native Godot integration     | Full native support           | All Godot projects  |
| **MP4** (Courtesy)    | H.264/AAC     | Cross-platform compatibility | Requires third-party plugins | Non-Godot use only  |
| **WebM** (Courtesy)   | VP9/Opus      | Web applications             | Limited via plugins          | Web exports/testing |
| **GIF** (Animated)    | Palette-based | Animations & UI elements     | Via AnimatedTexture or Sprite | UI animations, icons |

**Important Notes:**

* Only OGV format is officially supported by Godot without plugins
* MP4/WebM options are provided for convenience in non-Godot workflows
* GIF format is useful for small animations and UI elements (no audio support)
* For Godot projects, OGV is strongly recommended for:

  * Guaranteed compatibility across all platforms
  * No additional plugin dependencies
  * Consistent playback performance

### Sprite Atlas Generation

Convert videos into **sprite atlases** for 2D animations in Godot:

| Layout Mode    | Description                          |
| -------------- | ------------------------------------ |
| **Grid**       | Square arrangement (auto-calculated) |


**Resolution Options**: Low → Very High (or keep original) per frame
**Script to test**: When you generate a sprite atlas, you now get a ready-to-use .gd script
**Use Cases**: Character cycles, UI effects, particle animations, game object states, etc

### OGV Optimization Modes (Technical Specifications)

| Mode                   | Best Performance On    |
| ---------------------- | ---------------------- |
| **Standard**           | Default (recommended for most videos)      |
| **Constant FPS (CFR)** | UI elements            |
| **Weak Hardware**      | Mobile/Low-end devices |
| **Ideal Loop**         | Sprite animations      |
| **Controlled Bitrate** | Try to maintain the average bitrate        |
| **Mobile Optimized**   | Mobile games           |

### Quality Presets (Performance Characteristics)

| Preset        | Encoding Speed | Recommended Resolution Range |
| ------------- | -------------- | ---------------------------- |
| **Ultra**     | Very Slow      | 1080p-4K                     |
| **High**      | Slow           | 720p-1440p                   |
| **Balanced**  | Moderate       | 480p-1080p                   |
| **Optimized** | Fast           | 360p-720p                    |
| **Tiny**      | Very Fast      | 240p-480p                    |

*Conversion time varies based on resolution, FPS, and hardware capabilities*

## User Interface Features

* **Drag & drop** file input
* Real-time **video metadata display** (codec, resolution, duration)
* **Progress tracking** with percentage completion
* **Output folder** customization
* **Batch processing** of multiple files
* **Presets manager** for frequent configurations
* **Sprite atlas generator** with layout options

## General Technical Specifications

* **Resolution options**: 3840x2160 (4K) to 426x240 (240p)
* **FPS control**: Customizable (default: 30)
* **Audio options**: Preserve/remove audio track
* **File handling**: Automatic duplicate prevention
* **Settings**: Persist between sessions
* **Atlas generation**: PNG output with customizable frame extraction

## Installation & Requirements

1. Download the latest release
2. **No installation required** - portable executable
3. **FFmpeg included** - no additional dependencies

## Quick Start Guide

1. **Add files**: Drag videos into the window or use file dialog
2. **Choose output type**:

   * **Video Conversion**: Convert to OGV/MP4/WebM/GIF
   * **Sprite Atlas**: Generate PNG sprite sheets
3. **Configure**:

   * Select format/layout mode
   * Choose optimization settings
   * Set quality/resolution
4. **Convert**:

   * Set output folder (default: ./output)
   * Click "Convert" or "Generate Atlas"
