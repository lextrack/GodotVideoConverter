using System.Collections.Generic;

namespace GodotVideoConverter.Models
{
    public class VideoInfo
    {
        public bool IsValid { get; set; }
        public double Duration { get; set; }
        public int Width { get; set; }
        public int Height { get; set; }
        public double FrameRate { get; set; }
        public string VideoCodec { get; set; } = "";
        public string AudioCodec { get; set; } = "";
        public long BitRate { get; set; }
        public bool HasAudio { get; set; }
        public string AspectRatio => Width > 0 && Height > 0 ? $"{Width}:{Height}" : "Unknown";
        public string Resolution => Width > 0 && Height > 0 ? $"{Width}x{Height}" : "Unknown";
    }
}