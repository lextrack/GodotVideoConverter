using System.Collections.ObjectModel;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
        public ObservableCollection<string> Formats { get; } = new()
        {
            "OGV (Godot 4.x)", "MP4 (H.264/AAC)", "WebM (VP9/Opus)"
        };

        public ObservableCollection<string> Resolutions { get; } = new()
        {
            "3840x2160", "1920x1080", "1366x768", "1280x720", "1280x960",
            "1024x768", "854x480", "800x600", "640x360", "640x480",
            "512x512", "480x270", "426x240", "384x216", "256x256", "Keep original"
        };

        public ObservableCollection<string> AtlasResolutions { get; } = new()
        {
            "Low", "Medium", "High", "Very High", "Keep Original"
        };

        public ObservableCollection<string> Qualities { get; } = new()
        {
            "Ultra", "High", "Balanced", "Optimized", "Tiny"
        };

        public ObservableCollection<string> OgvModes { get; } = new()
        {
            "Standard", "Constant FPS (CFR)", "Optimized for weak hardware",
            "Ideal Loop", "Controlled Bitrate", "Mobile Optimized"
        };

        public ObservableCollection<string> AtlasModes { get; } = new()
        {
            "Grid", "Horizontal", "Vertical"
        };
    }
}