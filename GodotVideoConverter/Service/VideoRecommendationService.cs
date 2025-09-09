using GodotVideoConverter.Models;
using System.Collections.Generic;

namespace GodotVideoConverter.Services
{
    public class VideoRecommendationService
    {
        public string GetGodotRecommendations(VideoInfo videoInfo, bool keepAudio = true)
        {
            var builder = new VideoRecommendationBuilder(videoInfo, keepAudio);
            return builder.Build();
        }
    }

    internal class VideoRecommendationBuilder
    {
        private readonly VideoInfo _video;
        private readonly bool _keepAudio;
        private readonly List<string> _general = new();
        private readonly List<string> _resolution = new();
        private readonly List<string> _performance = new();
        private readonly List<string> _audio = new();
        private readonly List<string> _format = new();
        private readonly List<string> _specialCases = new();

        public VideoRecommendationBuilder(VideoInfo video, bool keepAudio)
        {
            _video = video;
            _keepAudio = keepAudio;
        }

        public string Build()
        {
            if (!_video.IsValid) return "Invalid video file";

            AnalyzeDuration();
            AnalyzeResolution();
            AnalyzeFrameRate();
            AnalyzeAudio();
            AnalyzeAspectRatio();
            AnalyzeFormat();

            return CompileFinalRecommendations();
        }

        private void AnalyzeDuration()
        {
            if (_video.Duration <= 10)
            {
                _general.Add("🔄 Short video - Perfect for UI animations or button effects");
                _specialCases.Add("💡 Use 'Ideal Loop' mode in OGV for seamless looping");
                if (_video.FrameRate < 30)
                    _performance.Add("💡 Increase to 30 FPS for smoother UI animations");
            }
            else if (_video.Duration <= 30)
            {
                _general.Add("🎬 Medium clip - Ideal for character animations or environmental loops");
                _performance.Add("💡 Try 'Standard' mode in OGV for a good balance");
            }
            else if (_video.Duration <= 60)
            {
                _general.Add("🎭 Long sequence - Great for cutscenes or character intros");
                _performance.Add("💡 Use 'Streaming Optimized' mode in OGV to save memory");
            }
            else if (_video.Duration <= 180)
            {
                _general.Add("🎪 Extended video - Suitable for intro cinematics or tutorials");
                _performance.Add("💡 Split into shorter clips for faster loading in Godot");
                _performance.Add("💡 Use 'Mobile Optimized' mode in OGV for mobile devices");
            }
            else
            {
                _general.Add("⏰ Very long video - May impact loading times");
                _performance.Add("⚠️ Large files possible with OGV; reduce resolution or FPS");
                _performance.Add("💡 Split into smaller clips or stream externally");
            }
        }

        private void AnalyzeResolution()
        {
            if (_video.Width > 1920 || _video.Height > 1080)
            {
                _resolution.Add("📺 High resolution detected");
                _performance.Add("⚠️ Large files possible with OGV; try 1080p or 720p to save space");
                if (_video.Duration <= 30)
                    _resolution.Add("💡 High-res is fine for short splash screens or cutscenes");
                else
                    _resolution.Add("💡 Use 1080p for most Godot projects, or 720p for mobiles");
            }
            else if (_video.Width <= 854 && _video.Height <= 480)
            {
                _resolution.Add("📱 Low resolution - Great for mobile or retro-style games");
                _performance.Add("💡 Use 'Mobile Optimized' mode in OGV for best performance");
            }
            else
            {
                _resolution.Add("🖼️ Standard resolution - Suitable for most Godot projects");
                _performance.Add("💡 Try 720p for mobiles or 1080p for desktop");
            }
        }

        private void AnalyzeFrameRate()
        {
            if (_video.FrameRate > 60)
            {
                if (_video.Duration <= 5)
                {
                    _specialCases.Add("🎯 High FPS short clip - Great for smooth UI effects");
                }
                else
                {
                    _performance.Add("⚡ High FPS detected");
                    _performance.Add("💡 Reduce to 30 FPS to save space with OGV");
                }
            }
            else if (_video.FrameRate < 24)
            {
                _performance.Add("🐌 Low FPS detected");
                _performance.Add("💡 Use 24-30 FPS for smooth cinematics or gameplay");
            }
            else
            {
                _performance.Add("✨ 24-30 FPS is ideal for OGV in Godot - balances smoothness and size");
            }
        }

        private void AnalyzeAudio()
        {
            if (_video.HasAudio)
            {
                if (_video.Duration <= 5)
                {
                    _audio.Add("🔊 Short clip with audio - Perfect for UI sounds or effects");
                }
                else if (_video.Duration > 60)
                {
                    _audio.Add("🎵 Long video with audio - Great for cutscenes");
                    _audio.Add("💡 Extract audio as OGG for better control in Godot");
                }
                else
                {
                    _audio.Add("🎬 Audio included - Good for character dialogues or ambient scenes");
                    _audio.Add("💡 Consider extracting audio as OGG for flexible control in Godot");
                }
            }
            else
            {
                _audio.Add("🔇 No audio - Ideal for background loops or visual effects");
                _format.Add("💡 Use OGV for best compatibility in Godot");
            }
        }

        private void AnalyzeAspectRatio()
        {
            string aspectRatio = GetSimplifiedAspectRatio();
            if (aspectRatio == "16:9")
            {
                _resolution.Add("📺 Widescreen (16:9) - Perfect for cutscenes or fullscreen videos");
            }
            else if (aspectRatio == "4:3")
            {
                _resolution.Add("📟 Classic 4:3 - Great for retro games or UI elements");
            }
            else if (aspectRatio == "1:1")
            {
                _resolution.Add("⬜ Square (1:1) - Ideal for icons or UI animations");
            }
            else
            {
                _resolution.Add("🎬 Non-standard aspect ratio - Crop or pad to match your game");
            }
        }

        private string GetSimplifiedAspectRatio()
        {
            if (_video.Width <= 0 || _video.Height <= 0) return "Unknown";

            int gcd = GetGCD(_video.Width, _video.Height);
            int w = _video.Width / gcd;
            int h = _video.Height / gcd;

            return $"{w}:{h}" switch
            {
                "16:9" => "16:9",
                "4:3" => "4:3",
                "1:1" => "1:1",
                "21:9" => "21:9",
                "3:2" => "3:2",
                _ => $"{w}:{h}"
            };
        }

        private int GetGCD(int a, int b)
        {
            while (b != 0)
            {
                int temp = b;
                b = a % b;
                a = temp;
            }
            return a;
        }

        private void AnalyzeFormat()
        {
            if (_video.VideoCodec.ToLower().Contains("h264"))
            {
                _format.Add("⚠️ MP4 (H.264) not supported in Godot; convert to OGV for compatibility");
                _format.Add("💡 Use MP4 only for non-Godot uses, like promotional videos");
            }
            else if (_video.VideoCodec.ToLower().Contains("vp9"))
            {
                _format.Add("⚠️ WebM (VP9) not supported in Godot; convert to OGV for compatibility");
                _format.Add("💡 Use WebM only for non-Godot uses, like web playback");
            }
            else
            {
                _format.Add("✅ OGV is the only format natively supported by Godot");
            }
        }

        private string CompileFinalRecommendations()
        {
            var allRecommendations = new List<string>();

            if (_general.Count > 0) allRecommendations.Add("🎯 GENERAL\n" + string.Join("\n", _general));
            if (_resolution.Count > 0) allRecommendations.Add("🖼️ RESOLUTION\n" + string.Join("\n", _resolution));
            if (_performance.Count > 0) allRecommendations.Add("⚡ PERFORMANCE\n" + string.Join("\n", _performance));
            if (_audio.Count > 0) allRecommendations.Add("🔊 AUDIO\n" + string.Join("\n", _audio));
            if (_format.Count > 0) allRecommendations.Add("📼 FORMAT\n" + string.Join("\n", _format));
            if (_specialCases.Count > 0) allRecommendations.Add("💎 SPECIAL CASES\n" + string.Join("\n", _specialCases));

            if (allRecommendations.Count == 0)
            {
                return "✅ Video looks perfect for Godot! Use OGV for best compatibility. 🎮";
            }

            return string.Join("\n\n", allRecommendations);
        }
    }
}