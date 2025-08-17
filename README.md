# Godot Video Converter

A specialized video conversion tool designed for **Godot Engine** developers, with optimized settings for game development workflows.

## 🎯 Purpose

Convert videos to Godot-compatible formats (especially OGV) with:
- Native Godot support without external plugins
- Game-oriented optimizations
- Batch processing capabilities
- Customizable output settings

## ✨ Key Features

### Supported Formats

| Format       | Codecs              | Primary Purpose         | Godot Support       | Recommended Usage          |
|--------------|---------------------|-------------------------|--------------------------|---------------------------|
| **OGV** (Recommended) | Theora/Vorbis | Native Godot integration | ✅ Full native support | All Godot projects |
| **MP4** (Courtesy) | H.264/AAC | Cross-platform compatibility | ❌ Requires third-party plugins | Non-Godot use only |
| **WebM** (Courtesy) | VP9/Opus | Web applications | ⚠️ Limited via plugins | Web exports/testing |

**Important Notes:**
- Only OGV format is officially supported by Godot without plugins
- MP4/WebM options are provided for convenience in non-Godot workflows
- For Godot projects, OGV is strongly recommended for:
  - Guaranteed compatibility across all platforms
  - No additional plugin dependencies
  - Consistent playback performance   |

### OGV Optimization Modes (Technical Specifications)
| Mode                      | GOP | Keyframe Interval | Best Performance On      |
|---------------------------|-----|-------------------|--------------------------|
| **Standard**              | 30  | Every 30 frames   | Desktop/Consoles         |
| **Constant FPS (CFR)**    | 15  | Fixed FPS         | UI elements              |
| **Weak Hardware**         | 60  | Every 60 frames   | Mobile/Low-end devices   |
| **Ideal Loop**            | 1   | Every frame       | Sprite animations        |
| **Streaming Optimized**   | 15  | Every 5 frames    | Live streaming           |
| **Mobile Optimized**      | 30  | Every 30 frames   | Mobile games             |

### Quality Presets (Performance Characteristics)
| Preset       | CRF/QP Value | Encoding Speed | Recommended Resolution Range |
|--------------|-------------|----------------|------------------------------|
| **Ultra**    | CRF 15      | Very Slow      | 1080p-4K                     |
| **High**     | CRF 18      | Slow           | 720p-1440p                   |
| **Balanced** | CRF 23      | Moderate       | 480p-1080p                   |
| **Optimized**| CRF 28      | Fast           | 360p-720p                    |
| **Tiny**     | CRF 35      | Very Fast      | 240p-480p                    |

*Conversion time varies based on resolution, FPS, and hardware capabilities*

## 🖥️ User Interface Features
- **Drag & drop** file input
- Real-time **video metadata display** (codec, resolution, duration)
- **Progress tracking** with percentage completion
- **Output folder** customization
- **Batch processing** of multiple files
- **Presets manager** for frequent configurations

## ⚙️ Technical Specifications
- **Resolution options**: 3840x2160 (4K) to 426x240 (240p)
- **FPS control**: Customizable (default: 30) with CFR option
- **Audio options**: Preserve/remove audio tracks
- **File handling**: Automatic duplicate prevention
- **Settings**: Persist between sessions

## 🎮 Why Use OGV in Godot?
- **Native support**: Zero-configuration playback
- **Cross-platform**: Identical behavior on all Godot targets
- **Performance**: Lightweight decoding suitable for games
- **Reliability**: No plugin dependencies or licensing issues

## 📦 Installation & Requirements
1. Download the latest release (Windows/macOS/Linux)
2. **No installation required** - portable executable
3. **FFmpeg included** - no additional dependencies

## 🚀 Quick Start Guide
1. **Add files**: Drag videos into the window or use file dialog
2. **Configure**:
   - Select format (OGV for Godot)
   - Choose optimization mode
   - Set quality preset
3. **Convert**:
   - Set output folder (default: ./output)
   - Click "Convert"