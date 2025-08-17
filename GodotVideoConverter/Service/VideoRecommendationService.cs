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

            return CompileFinalRecommendations();
        }

        private void AnalyzeDuration()
        {
            if (_video.Duration <= 10)
            {
                _general.Add("🔄 Short video detected - Perfect for UI animations, button effects, or loading screens");
                _specialCases.Add("💡 Consider 'Ideal Loop' mode for seamless cycling");
                if (_video.FrameRate < 30)
                    _performance.Add("💡 For smooth UI animations, consider increasing to 30+ FPS");
            }
            else if (_video.Duration <= 30)
            {
                _general.Add("🎬 Medium clip - Ideal for character animations, spell effects, or environmental loops");
                _performance.Add("💡 'Standard' or 'Streaming Optimized' modes work well for this length");
            }
            else if (_video.Duration <= 60)
            {
                _general.Add("🎭 Long sequence - Great for cutscenes, character introductions, or gameplay demonstrations");
                _performance.Add("💡 'Streaming Optimized' mode recommended for better memory management");
            }
            else if (_video.Duration <= 180)
            {
                _general.Add("🎪 Extended video - Suitable for intro cinematics, tutorials, or story sequences");
                _performance.Add("💡 Consider splitting into chapters for better loading performance");
                _performance.Add("💡 'Mobile Optimized' mode if targeting mobile devices");
            }
            else
            {
                _general.Add("⏰ Very long content - Consider if this needs to be a video or could be streamed externally");
                _performance.Add("⚠️ Large videos can impact game loading times and memory usage");
                _performance.Add("💡 Consider splitting into smaller segments or using external streaming");
            }
        }

        private void AnalyzeResolution()
        {
            if (_video.Width > 1920 || _video.Height > 1080)
            {
                _resolution.Add("📺 High resolution detected");
                if (_video.Duration > 30)
                {
                    _performance.Add("⚠️ Large files ahead! Consider reducing resolution for better performance");
                    _performance.Add("💡 1080p is usually sufficient for most Godot projects");
                }
                else
                {
                    _resolution.Add("💡 High-res short clips are fine for splash screens or high-quality cutscenes");
                }
            }
            else if (_video.Width <= 854 && _video.Height <= 480)
            {
                _resolution.Add("📱 Lower resolution - Excellent for mobile games or retro-style projects");
            }
        }

        private void AnalyzeFrameRate()
        {
            if (_video.FrameRate > 60)
            {
                if (_video.Duration <= 5)
                {
                    _specialCases.Add("🎯 High FPS short clip - Great for smooth UI effects or particle showcases");
                }
                else
                {
                    _performance.Add("⚡ Very high FPS detected");
                    _performance.Add("💡 60+ FPS is rarely needed in Godot videos - consider reducing to 30-60 FPS");
                    _performance.Add("💡 Higher FPS = larger file sizes without much visual benefit in most cases");
                }
            }
            else if (_video.FrameRate < 23)
            {
                _performance.Add("🐌 Low FPS detected");
                if (_video.Duration <= 10)
                {
                    _performance.Add("💡 For smooth gameplay videos, consider 24-30 FPS minimum");
                }
                else
                {
                    _performance.Add("💡 24+ FPS recommended for cinematic feel, 30 FPS for smoother motion");
                }
            }
            else if (_video.FrameRate >= 24 && _video.FrameRate <= 30)
            {
                _performance.Add("✨ Perfect FPS range for Godot videos - good balance of smoothness and file size");
            }
        }

        private void AnalyzeAudio()
        {
            if (_video.HasAudio)
            {
                if (_video.Duration <= 5)
                {
                    _audio.Add("🔊 Short video with audio - Perfect for UI sounds, notification effects");
                }
                else if (_video.Duration > 60)
                {
                    _audio.Add("🎵 Long video with audio - Great for cutscenes and story content");
                    _audio.Add("💡 Consider separate audio files for music to enable volume control");
                }
                else
                {
                    _audio.Add("🎬 Audio included - Good for character dialogues and ambient scenes");
                }
            }
            else
            {
                if (_video.Duration > 10 && _video.VideoCodec.ToLower().Contains("h264"))
                {
                    _format.Add("🔇 No audio detected - OGV format might be more efficient than H.264");
                }
                else if (_video.Duration <= 5)
                {
                    _audio.Add("🔇 Silent clip - Perfect for background loops or visual effects");
                }
            }
        }

        private void AnalyzeAspectRatio()
        {
            string aspectRatio = GetSimplifiedAspectRatio();
            if (aspectRatio == "16:9")
            {
                _resolution.Add("📺 Standard widescreen - Perfect for cutscenes and fullscreen videos");
            }
            else if (aspectRatio == "4:3")
            {
                _resolution.Add("📟 Classic ratio - Great for retro games or UI elements");
            }
            else if (aspectRatio == "1:1")
            {
                _resolution.Add("⬜ Square format - Excellent for icons, profile pictures, or UI animations");
            }
            else if (_video.Width > _video.Height * 2)
            {
                _resolution.Add("🎬 Ultra-wide format - Consider if this fits your game's aspect ratio");
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
                return "✅ Video looks perfect for Godot! 🎮";
            }

            return string.Join("\n\n", allRecommendations);
        }
    }
}