using GodotVideoConverter.Models;
using ImageMagick;
using System;
using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Globalization;

namespace GodotVideoConverter.Services
{
    public class VideoConversionService
    {
        private readonly string _ffmpegPath;
        private readonly string _ffprobePath;
        private Process? _currentProcess;
        private bool _disposed = false;
        private readonly VideoRecommendationService _recommendationService;
        private readonly int _maxParallelSegments;
        private readonly SemaphoreSlim _processSemaphore;

        private readonly object _processLock = new object();

        public VideoConversionService(string baseDir)
        {
            _ffmpegPath = Path.Combine(baseDir, "ffmpeg.exe");
            _ffprobePath = Path.Combine(baseDir, "ffprobe.exe");
            if (!File.Exists(_ffmpegPath) || !File.Exists(_ffprobePath))
            {
                throw new FileNotFoundException("FFmpeg or FFprobe not found in the specified directory.");
            }
            _recommendationService = new VideoRecommendationService();
            _maxParallelSegments = Math.Max(1, Environment.ProcessorCount - 1);
            _processSemaphore = new SemaphoreSlim(_maxParallelSegments, _maxParallelSegments);
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
                    Debug.WriteLine($"FFprobe failed with exit code {process.ExitCode}. Error: {error}");
                    return videoInfo;
                }

                var jsonDoc = JsonDocument.Parse(output);
                var root = jsonDoc.RootElement;

                if (root.TryGetProperty("format", out var format))
                {
                    if (format.TryGetProperty("duration", out var duration))
                    {
                        string durationStr = duration.GetString() ?? "";
                        Debug.WriteLine($"Raw duration string from FFprobe: '{durationStr}'");

                        if (double.TryParse(durationStr, NumberStyles.Float, CultureInfo.InvariantCulture, out var dur))
                        {
                            videoInfo.Duration = dur;
                            Debug.WriteLine($"Parsed duration: {dur} seconds");
                        }
                        else
                        {
                            Debug.WriteLine($"Failed to parse duration: '{durationStr}'");
                            if (TryParseAlternativeDuration(durationStr, out var altDur))
                            {
                                videoInfo.Duration = altDur;
                                Debug.WriteLine($"Alternative parsing succeeded: {altDur} seconds");
                            }
                        }
                    }

                    if (format.TryGetProperty("bit_rate", out var bitrate))
                    {
                        string bitrateStr = bitrate.GetString() ?? "";
                        if (long.TryParse(bitrateStr, NumberStyles.Integer, CultureInfo.InvariantCulture, out var br))
                        {
                            videoInfo.BitRate = br;
                        }
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
                                            double.TryParse(parts[0], NumberStyles.Float, CultureInfo.InvariantCulture, out var num) &&
                                            double.TryParse(parts[1], NumberStyles.Float, CultureInfo.InvariantCulture, out var den) &&
                                            den != 0)
                                        {
                                            videoInfo.FrameRate = num / den;
                                        }
                                    }
                                }

                                if (videoInfo.Duration <= 0 && stream.TryGetProperty("duration", out var streamDuration))
                                {
                                    string streamDurStr = streamDuration.GetString() ?? "";
                                    if (double.TryParse(streamDurStr, NumberStyles.Float, CultureInfo.InvariantCulture, out var streamDur))
                                    {
                                        videoInfo.Duration = streamDur;
                                        Debug.WriteLine($"Using video stream duration: {streamDur} seconds");
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

                if (videoInfo.Duration > 0)
                {
                    if (videoInfo.Duration > 86400)
                    {
                        Debug.WriteLine($"Warning: Extremely long duration detected: {videoInfo.Duration}s ({videoInfo.Duration / 3600:F1} hours)");
                        Debug.WriteLine("This might indicate a parsing error. Consider checking the video file.");
                    }

                    if (videoInfo.Duration > 3600)
                    {
                        var alternativeDuration = await GetDurationDirectly(file);
                        if (alternativeDuration > 0 && alternativeDuration < videoInfo.Duration)
                        {
                            Debug.WriteLine($"Using alternative duration: {alternativeDuration} seconds");
                            videoInfo.Duration = alternativeDuration;
                        }
                    }
                }

                videoInfo.IsValid = videoInfo.Duration > 0 && videoInfo.Width > 0 && videoInfo.Height > 0;
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error in GetVideoInfoAsync: {ex.Message}");
            }

            return videoInfo;
        }

        private bool TryParseAlternativeDuration(string durationStr, out double duration)
        {
            duration = 0;
            if (string.IsNullOrEmpty(durationStr))
                return false;

            var match = Regex.Match(durationStr, @"(\d+):(\d+):(\d+(?:\.\d+)?)");
            if (match.Success)
            {
                try
                {
                    double hours = double.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
                    double minutes = double.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture);
                    double seconds = double.Parse(match.Groups[3].Value, CultureInfo.InvariantCulture);
                    duration = hours * 3600 + minutes * 60 + seconds;
                    return true;
                }
                catch
                {
                    return false;
                }
            }
            return false;
        }

        private async Task<double> GetDurationDirectly(string file)
        {
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = _ffprobePath,
                    Arguments = $"-v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 \"{file}\"",
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(psi);
                if (process == null) return 0;

                string output = await process.StandardOutput.ReadToEndAsync();
                await process.WaitForExitAsync();

                if (process.ExitCode == 0 && double.TryParse(output.Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out var duration))
                {
                    return duration;
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error in GetDurationDirectly: {ex.Message}");
            }
            return 0;
        }

        public async Task<bool> ValidateVideoFileAsync(string file)
        {
            try
            {
                var videoInfo = await GetVideoInfoAsync(file);
                return videoInfo.IsValid;
            }
            catch
            {
                return false;
            }
        }

        public async Task ConvertAsync(string inputFile, string outputFile, string arguments, double duration, IProgress<int> progress)
        {
            await RunFFmpegAsync(arguments, duration, outputFile, progress);
        }

        public async Task<List<string>> ConvertToSpriteAtlasAsync(string inputFile, string outputFile, int fps, string scaleFilter, string atlasMode, IProgress<int> progress)
        {
            var frameFiles = new List<string>();
            string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            Directory.CreateDirectory(tempDir);

            try
            {
                string fpsFilter = fps > 0 ? $"fps={fps}" : "";
                string filterChain = "";
                if (!string.IsNullOrEmpty(fpsFilter))
                {
                    filterChain = fpsFilter;
                }
                if (!string.IsNullOrEmpty(scaleFilter))
                {
                    if (!string.IsNullOrEmpty(filterChain))
                    {
                        filterChain += ",";
                    }
                    filterChain += scaleFilter;
                }

                string vfArg = !string.IsNullOrEmpty(filterChain) ? $"-vf {filterChain}" : "";
                string args = $"-i \"{inputFile}\" {vfArg} -pix_fmt rgba \"{Path.Combine(tempDir, "frame_%04d.png")}\" -y";

                double duration = await GetVideoDurationAsync(inputFile);
                await RunFFmpegAsync(args, duration, null, progress);

                frameFiles.AddRange(Directory.GetFiles(tempDir, "frame_*.png").OrderBy(f => f));

                using var collection = new MagickImageCollection();
                foreach (var frame in frameFiles)
                {
                    collection.Add(new MagickImage(frame));
                }

                using var result = CreateGridAtlas(collection, frameFiles.Count, progress);
                result.Write(outputFile);
            }
            finally
            {
                try
                {
                    Directory.Delete(tempDir, true);
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error cleaning temp directory: {ex.Message}");
                }
            }

            return frameFiles;
        }

        private IMagickImage<ushort> CreateGridAtlas(MagickImageCollection collection, int frameCount, IProgress<int> progress = null)
        {
            int columns = (int)Math.Ceiling(Math.Sqrt(frameCount));
            int rows = (int)Math.Ceiling((double)frameCount / columns);

            var settings = new MontageSettings
            {
                Geometry = new MagickGeometry((uint)collection[0].Width, (uint)collection[0].Height),
                TileGeometry = new MagickGeometry((uint)columns, (uint)rows),
                BackgroundColor = MagickColors.Transparent,
                BorderWidth = 0
            };

            var result = collection.Montage(settings);
            progress?.Report(100);
            return result;
        }

        private async Task RunFFmpegAsync(string arguments, double totalSeconds, string? outputFile, IProgress<int> progress, CancellationToken cancellationToken = default)
        {
            await _processSemaphore.WaitAsync(cancellationToken);

            try
            {
                using var cancellationTokenSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);

                var psi = new ProcessStartInfo
                {
                    FileName = _ffmpegPath,
                    Arguments = arguments,
                    RedirectStandardError = true,
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                Process? process = null;

                lock (_processLock)
                {
                    if (_disposed)
                    {
                        throw new ObjectDisposedException(nameof(VideoConversionService));
                    }

                    process = Process.Start(psi);
                    if (process == null)
                        throw new InvalidOperationException("Failed to start FFmpeg process");

                    _currentProcess = process;
                }

                try
                {
                    var timeRegex = new Regex(@"time=(\d+):(\d+):(\d+(?:\.\d+)?)", RegexOptions.Compiled);
                    var lastProgress = 0;
                    var progressLock = new object();

                    var stderrTask = Task.Run(async () =>
                    {
                        try
                        {
                            using var reader = process.StandardError;
                            string? line;

                            while ((line = await reader.ReadLineAsync()) != null)
                            {
                                cancellationToken.ThrowIfCancellationRequested();

                                if (string.IsNullOrEmpty(line)) continue;

                                var match = timeRegex.Match(line);
                                if (match.Success)
                                {
                                    try
                                    {
                                        double hours = double.Parse(match.Groups[1].Value, CultureInfo.InvariantCulture);
                                        double minutes = double.Parse(match.Groups[2].Value, CultureInfo.InvariantCulture);
                                        double seconds = double.Parse(match.Groups[3].Value, CultureInfo.InvariantCulture);

                                        double currentSeconds = hours * 3600 + minutes * 60 + seconds;
                                        int percentComplete = totalSeconds > 0
                                            ? (int)Math.Min((currentSeconds / totalSeconds) * 100, 100)
                                            : 0;

                                        lock (progressLock)
                                        {
                                            if (percentComplete > lastProgress)
                                            {
                                                lastProgress = percentComplete;
                                                progress?.Report(percentComplete);
                                            }
                                        }
                                    }
                                    catch (FormatException)
                                    {
                                        continue;
                                    }
                                }

                                if (line.Contains("No such file or directory") ||
                                    line.Contains("Invalid data found") ||
                                    line.Contains("Permission denied"))
                                {
                                    throw new InvalidOperationException($"FFmpeg error: {line}");
                                }
                            }
                        }
                        catch (OperationCanceledException)
                        {
                        }
                        catch (Exception ex) when (!(ex is OperationCanceledException))
                        {
                            Debug.WriteLine($"Error reading FFmpeg stderr: {ex.Message}");
                        }
                    }, cancellationToken);

                    var stdoutTask = Task.Run(async () =>
                    {
                        try
                        {
                            using var reader = process.StandardOutput;
                            while (await reader.ReadLineAsync() != null)
                            {
                                cancellationToken.ThrowIfCancellationRequested();
                            }
                        }
                        catch (OperationCanceledException)
                        {
                        }
                    }, cancellationToken);

                    var processTask = Task.Run(async () =>
                    {
                        await process.WaitForExitAsync(cancellationToken);
                    }, cancellationToken);

                    var timeoutTask = Task.Delay(TimeSpan.FromMinutes(5), cancellationToken);
                    var completedTask = await Task.WhenAny(processTask, timeoutTask);

                    if (completedTask == timeoutTask)
                    {
                        throw new TimeoutException("FFmpeg conversion timed out after 5 minutes");
                    }

                    cancellationTokenSource.Cancel();

                    try
                    {
                        await Task.WhenAll(stderrTask, stdoutTask);
                    }
                    catch (OperationCanceledException)
                    {
                    }

                    if (process.ExitCode != 0)
                    {
                        throw new InvalidOperationException($"Conversion failed with exit code {process.ExitCode}");
                    }

                    if (outputFile != null && !File.Exists(outputFile))
                    {
                        throw new InvalidOperationException("Output file was not created");
                    }

                    if (outputFile != null)
                    {
                        var fileInfo = new FileInfo(outputFile);
                        if (fileInfo.Length == 0)
                        {
                            File.Delete(outputFile);
                            throw new InvalidOperationException("Output file is empty - conversion may have failed");
                        }
                    }

                    progress?.Report(100);
                }
                catch (OperationCanceledException)
                {
                    if (outputFile != null && File.Exists(outputFile))
                    {
                        try { File.Delete(outputFile); } catch { }
                    }
                    throw;
                }
                catch (Exception)
                {
                    if (outputFile != null && File.Exists(outputFile))
                    {
                        try { File.Delete(outputFile); } catch { }
                    }
                    throw;
                }
                finally
                {
                    lock (_processLock)
                    {
                        if (_currentProcess == process)
                        {
                            _currentProcess = null;
                        }
                    }

                    try
                    {
                        if (process != null && !process.HasExited)
                        {
                            process.Kill();
                            process.WaitForExit(1000);
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"Error cleaning up process: {ex.Message}");
                    }
                    finally
                    {
                        process?.Dispose();
                    }
                }
            }
            finally
            {
                _processSemaphore.Release();
            }
        }

        public void CancelCurrentConversion()
        {
            Process? processToCancel = null;

            lock (_processLock)
            {
                processToCancel = _currentProcess;
                _currentProcess = null;
            }

            if (processToCancel != null)
            {
                try
                {
                    if (!processToCancel.HasExited)
                    {
                        processToCancel.CloseMainWindow();

                        if (!processToCancel.WaitForExit(2000))
                        {
                            processToCancel.Kill();
                            processToCancel.WaitForExit(1000);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error cancelling conversion: {ex.Message}");
                }
                finally
                {
                    try
                    {
                        processToCancel.Dispose();
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"Error disposing process: {ex.Message}");
                    }
                }
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
                    lock (_processLock)
                    {
                        _disposed = true;
                        CancelCurrentConversion();
                    }
                    _processSemaphore?.Dispose();
                }
            }
        }

        ~VideoConversionService()
        {
            Dispose(false);
        }
    }
}