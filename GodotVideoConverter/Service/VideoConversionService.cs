using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using GodotVideoConverter.Models;
using GodotVideoConverter.Services;

namespace GodotVideoConverter.Services
{
    public class VideoConversionService
    {
        private readonly string _ffmpegPath;
        private readonly string _ffprobePath;
        private Process? _currentProcess;
        private bool _disposed = false;
        private readonly VideoRecommendationService _recommendationService;

        public VideoConversionService(string baseDir)
        {
            _ffmpegPath = Path.Combine(baseDir, "ffmpeg.exe");
            _ffprobePath = Path.Combine(baseDir, "ffprobe.exe");
            _recommendationService = new VideoRecommendationService();
        }

        public async Task<double> GetVideoDurationAsync(string file)
        {
            var videoInfo = await GetVideoInfoAsync(file);
            return videoInfo.Duration;
        }

        public async Task<VideoInfo> GetVideoInfoAsync(string file)
        {
            var videoInfo = new VideoInfo();

            try
            {
                var fileInfo = new FileInfo(file);

                var psi = new ProcessStartInfo
                {
                    FileName = _ffprobePath,
                    Arguments = $"-v quiet -print_format json -show_format -show_streams \"{file}\"",
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(psi);
                if (process == null) return videoInfo;

                string output = await process.StandardOutput.ReadToEndAsync();
                string error = await process.StandardError.ReadToEndAsync();
                await process.WaitForExitAsync();

                if (process.ExitCode != 0 || string.IsNullOrEmpty(output))
                {
                    return videoInfo;
                }

                var jsonDoc = JsonDocument.Parse(output);
                var root = jsonDoc.RootElement;

                if (root.TryGetProperty("format", out var format))
                {
                    if (format.TryGetProperty("duration", out var duration))
                    {
                        if (double.TryParse(duration.GetString(), out var dur))
                            videoInfo.Duration = dur;
                    }

                    if (format.TryGetProperty("bit_rate", out var bitrate))
                    {
                        if (long.TryParse(bitrate.GetString(), out var br))
                            videoInfo.BitRate = br;
                    }
                }

                if (root.TryGetProperty("streams", out var streams))
                {
                    foreach (var stream in streams.EnumerateArray())
                    {
                        if (stream.TryGetProperty("codec_type", out var codecType))
                        {
                            string type = codecType.GetString() ?? "";

                            if (type == "video")
                            {
                                if (stream.TryGetProperty("width", out var width))
                                    videoInfo.Width = width.GetInt32();

                                if (stream.TryGetProperty("height", out var height))
                                    videoInfo.Height = height.GetInt32();

                                if (stream.TryGetProperty("codec_name", out var vcodec))
                                    videoInfo.VideoCodec = vcodec.GetString() ?? "";

                                if (stream.TryGetProperty("r_frame_rate", out var frameRate))
                                {
                                    string fpsStr = frameRate.GetString() ?? "";
                                    if (fpsStr.Contains('/'))
                                    {
                                        var parts = fpsStr.Split('/');
                                        if (parts.Length == 2 &&
                                            double.TryParse(parts[0], out var num) &&
                                            double.TryParse(parts[1], out var den) &&
                                            den != 0)
                                        {
                                            videoInfo.FrameRate = num / den;
                                        }
                                    }
                                }
                            }
                            else if (type == "audio")
                            {
                                videoInfo.HasAudio = true;
                                if (stream.TryGetProperty("codec_name", out var acodec))
                                    videoInfo.AudioCodec = acodec.GetString() ?? "";
                            }
                        }
                    }
                }

                videoInfo.IsValid = videoInfo.Duration > 0 && videoInfo.Width > 0 && videoInfo.Height > 0;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error getting video info: {ex.Message}");
            }

            return videoInfo;
        }

        public async Task<bool> ValidateVideoFileAsync(string file)
        {
            if (!File.Exists(file))
                return false;

            var videoInfo = await GetVideoInfoAsync(file);
            return videoInfo.IsValid;
        }

        public async Task ConvertAsync(string inputFile, string outputFile, string arguments, double totalSeconds, IProgress<int> progress)
        {
            var psi = new ProcessStartInfo
            {
                FileName = _ffmpegPath,
                Arguments = arguments,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            _currentProcess = Process.Start(psi);
            if (_currentProcess == null) return;

            var regex = new Regex(@"time=(\d+):(\d+):(\d+\.?\d*)");

            while (!_currentProcess.StandardError.EndOfStream)
            {
                string? line = await _currentProcess.StandardError.ReadLineAsync();
                if (line == null) continue;

                var match = regex.Match(line);
                if (match.Success)
                {
                    double h = double.Parse(match.Groups[1].Value);
                    double m = double.Parse(match.Groups[2].Value);
                    double s = double.Parse(match.Groups[3].Value);

                    double current = h * 3600 + m * 60 + s;
                    int percent = (int)(current / totalSeconds * 100);
                    progress.Report(Math.Min(percent, 100));
                }
            }

            await _currentProcess.WaitForExitAsync();
            progress.Report(100);
            _currentProcess = null;
        }

        public void CancelCurrentConversion()
        {
            try
            {
                if (_currentProcess != null && !_currentProcess.HasExited)
                {
                    _currentProcess.Kill();
                    _currentProcess.WaitForExit(1000);
                    _currentProcess = null;
                }
            }
            catch
            {

            }
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (!_disposed)
            {
                if (disposing)
                {
                    CancelCurrentConversion();
                }
                _disposed = true;
            }
        }

        ~VideoConversionService()
        {
            Dispose(false);
        }
    }
}
