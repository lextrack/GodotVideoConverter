using GodotVideoConverter.Models;
using GodotVideoConverter.Services;
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

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

        public VideoConversionService(string baseDir)
        {
            _ffmpegPath = Path.Combine(baseDir, "ffmpeg.exe");
            _ffprobePath = Path.Combine(baseDir, "ffprobe.exe");
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

        public async Task ConvertToSpriteAtlasAsync(string inputFile, string outputFile, int fps, string scaleFilter, string atlasMode, IProgress<int> progress)
        {
            string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            Directory.CreateDirectory(tempDir);

            try
            {
                progress?.Report(5);
                var videoInfo = await GetVideoInfoAsync(inputFile);
                ValidateVideoForAtlas(videoInfo, fps);
                progress?.Report(10);

                bool useParallel = videoInfo.Duration > 15.0 && _maxParallelSegments > 1;

                if (useParallel)
                {
                    Debug.WriteLine("Using parallel extraction");
                    var segments = CalculateOptimalSegments(videoInfo.Duration, fps);
                    await ExtractFramesParallelAsync(inputFile, tempDir, fps, scaleFilter, videoInfo, segments, progress);
                }
                else
                {
                    Debug.WriteLine("Using sequential extraction");
                    await ExtractFramesSequentialAsync(inputFile, tempDir, fps, scaleFilter, videoInfo, progress);
                }

                progress?.Report(70);
                await CreateStreamingAtlasAsync(tempDir, outputFile, atlasMode, progress);
                progress?.Report(100);
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Atlas generation error: {ex.Message}");
                throw;
            }
            finally
            {
                CleanupTempDirectory(tempDir);
            }
        }

        private async Task CreateStreamingAtlasAsync(string tempDir, string outputFile, string atlasMode, IProgress<int> progress)
        {
            var frameFiles = Directory.GetFiles(tempDir, "frame_*.png");
            Array.Sort(frameFiles);

            Debug.WriteLine($"Creating atlas with {frameFiles.Length} frames");

            if (frameFiles.Length == 0)
                throw new InvalidOperationException("No frames to process");

            Size frameSize = GetFrameSize(frameFiles[0]);
            var layout = CalculateOptimalLayout(frameFiles.Length, frameSize, atlasMode);

            Debug.WriteLine($"Atlas layout: {layout.cols}x{layout.rows}, Frame size: {frameSize}");

            long totalWidth = (long)frameSize.Width * layout.cols;
            long totalHeight = (long)frameSize.Height * layout.rows;

            ValidateAtlasSize(totalWidth, totalHeight, frameFiles.Length, layout);

            await CreateAtlasSequentialAsync(frameFiles, outputFile, frameSize, layout, progress);

            Debug.WriteLine("Atlas creation completed");
        }

        private async Task CreateAtlasSequentialAsync(string[] frameFiles, string outputFile, Size frameSize, (int cols, int rows) layout, IProgress<int> progress)
        {
            int atlasWidth = frameSize.Width * layout.cols;
            int atlasHeight = frameSize.Height * layout.rows;

            using var atlas = new Bitmap(atlasWidth, atlasHeight, PixelFormat.Format32bppArgb);
            using var graphics = Graphics.FromImage(atlas);

            graphics.Clear(Color.Transparent);
            graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
            graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;

            for (int i = 0; i < frameFiles.Length; i++)
            {
                try
                {
                    var pos = GetFramePosition(i, layout.cols, layout.rows, "grid");
                    int x = pos.col * frameSize.Width;
                    int y = pos.row * frameSize.Height;

                    using var frame = Image.FromFile(frameFiles[i]);
                    graphics.DrawImage(frame, x, y, frameSize.Width, frameSize.Height);

                    if (i % 10 == 0)
                    {
                        int progressPercent = 75 + (int)((i + 1) * 24.0 / frameFiles.Length);
                        progress?.Report(progressPercent);
                        Debug.WriteLine($"Atlas progress: {i + 1}/{frameFiles.Length} frames");

                        await Task.Yield();
                    }
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"Error processing frame {i}: {ex.Message}");
                    throw;
                }
            }

            atlas.Save(outputFile, ImageFormat.Png);
        }

        private void ValidateAtlasSize(long totalWidth, long totalHeight, int frameCount, (int cols, int rows) layout)
        {
            const int MAX_SIZE = 16384;
            if (totalWidth > MAX_SIZE || totalHeight > MAX_SIZE)
            {
                throw new InvalidOperationException(
                    $"Atlas too large: {totalWidth}x{totalHeight} (maximum: {MAX_SIZE}x{MAX_SIZE})\n" +
                    $"Frames: {frameCount}, Layout: {layout.cols}x{layout.rows}");
            }
        }

        private Size GetFrameSize(string framePath)
        {
            using var frame = Image.FromFile(framePath);
            return frame.Size;
        }

        private class VideoSegment
        {
            public int Index { get; set; }
            public double StartTime { get; set; }
            public double Duration { get; set; }
            public string TempDir { get; set; } = string.Empty;
        }

        private List<VideoSegment> CalculateOptimalSegments(double duration, int fps)
        {
            const double MAX_SEGMENT_DURATION = 10.0;
            int segmentCount = Math.Min(_maxParallelSegments, (int)Math.Ceiling(duration / MAX_SEGMENT_DURATION));
            double segmentDuration = duration / segmentCount;

            var segments = new List<VideoSegment>();
            for (int i = 0; i < segmentCount; i++)
            {
                segments.Add(new VideoSegment
                {
                    Index = i,
                    StartTime = i * segmentDuration,
                    Duration = Math.Min(segmentDuration, duration - (i * segmentDuration)),
                    TempDir = Path.Combine(Path.GetTempPath(), $"segment_{i}_{Guid.NewGuid()}")
                });
            }

            return segments;
        }

        private async Task ExtractFramesSequentialAsync(string inputFile, string tempDir, int fps, string scaleFilter, VideoInfo videoInfo, IProgress<int> progress)
        {
            string frameExtractArgs = BuildVFRCompatibleArgs(inputFile, tempDir, fps, scaleFilter, videoInfo);

            var extractProcess = await ExtractFramesWithTimeout(frameExtractArgs, TimeSpan.FromMinutes(5), progress);
            extractProcess?.Dispose();
        }

        private async Task ExtractFramesParallelAsync(string inputFile, string tempDir, int fps, string scaleFilter, VideoInfo videoInfo, List<VideoSegment> segments, IProgress<int> progress)
        {
            try
            {
                Debug.WriteLine($"Starting parallel extraction with {segments.Count} segments");

                using var cts = new CancellationTokenSource(TimeSpan.FromMinutes(10));
                var extractionTasks = segments.Select(segment =>
                    ExtractSegmentFramesAsync(inputFile, segment, fps, scaleFilter, videoInfo, cts.Token));

                await Task.WhenAll(extractionTasks);

                Debug.WriteLine("All segments extracted, merging...");
                await MergeSegmentFramesAsync(segments, tempDir, progress);
                Debug.WriteLine("Merge completed");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Parallel extraction failed: {ex.Message}, falling back to sequential");

                foreach (var segment in segments)
                {
                    CleanupTempDirectory(segment.TempDir);
                }

                await ExtractFramesSequentialAsync(inputFile, tempDir, fps, scaleFilter, videoInfo, progress);
            }
        }

        private async Task ExtractSegmentFramesAsync(string inputFile, VideoSegment segment, int fps, string scaleFilter, VideoInfo videoInfo, CancellationToken cancellationToken)
        {
            await _processSemaphore.WaitAsync(cancellationToken);

            try
            {
                Debug.WriteLine($"Processing segment {segment.Index}: {segment.StartTime:F1}s - {segment.StartTime + segment.Duration:F1}s");

                Directory.CreateDirectory(segment.TempDir);

                string args = BuildSegmentExtractionArgs(inputFile, segment, fps, scaleFilter, videoInfo);

                var psi = new ProcessStartInfo
                {
                    FileName = _ffmpegPath,
                    Arguments = args,
                    RedirectStandardError = true,
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var process = Process.Start(psi);
                if (process == null)
                    throw new InvalidOperationException($"Could not start FFmpeg for segment {segment.Index}");

                var lastActivity = DateTime.Now;
                var errorLines = new List<string>();

                var monitorTask = Task.Run(async () =>
                {
                    try
                    {
                        using var reader = process.StandardError;
                        string line;
                        while ((line = await reader.ReadLineAsync()) != null)
                        {
                            errorLines.Add(line);
                            if (line.Contains("frame=") || line.Contains("time="))
                            {
                                lastActivity = DateTime.Now;
                            }
                        }
                    }
                    catch { }
                });

                using var registration = cancellationToken.Register(() =>
                {
                    try
                    {
                        if (!process.HasExited)
                            process.Kill();
                    }
                    catch { }
                });

                var processTask = process.WaitForExitAsync(cancellationToken);
                var timeoutTask = Task.Delay(TimeSpan.FromMinutes(5), cancellationToken);

                var progressCheckTask = Task.Run(async () =>
                {
                    while (!process.HasExited && !cancellationToken.IsCancellationRequested)
                    {
                        await Task.Delay(20000, cancellationToken);
                        if (DateTime.Now - lastActivity > TimeSpan.FromMinutes(2))
                        {
                            throw new TimeoutException($"Segment {segment.Index} stuck - no activity for 2 minutes");
                        }
                    }
                }, cancellationToken);

                var completedTask = await Task.WhenAny(processTask, timeoutTask, progressCheckTask);

                if (completedTask == timeoutTask)
                {
                    throw new TimeoutException($"Segment {segment.Index} timed out after 5 minutes");
                }

                if (completedTask == progressCheckTask)
                {
                    await progressCheckTask;
                }

                await monitorTask;

                if (process.ExitCode != 0)
                {
                    string error = errorLines.Count > 0 ? string.Join("\n", errorLines.TakeLast(3)) : "Unknown error";
                    throw new InvalidOperationException($"Segment {segment.Index} failed: {error}");
                }

                var frameCount = Directory.GetFiles(segment.TempDir, "frame_*.png").Length;
                if (frameCount == 0)
                {
                    throw new InvalidOperationException($"Segment {segment.Index} produced no frames - FFmpeg may have failed silently");
                }

                Debug.WriteLine($"Segment {segment.Index} completed: {frameCount} frames");
            }
            finally
            {
                _processSemaphore.Release();
            }
        }

        private async Task MergeSegmentFramesAsync(List<VideoSegment> segments, string tempDir, IProgress<int> progress)
        {
            var allFramePaths = new List<(string path, double timeCode)>();

            foreach (var segment in segments.OrderBy(s => s.Index))
            {
                var segmentFrames = Directory.GetFiles(segment.TempDir, "frame_*.png");

                foreach (var framePath in segmentFrames)
                {
                    string fileName = Path.GetFileNameWithoutExtension(framePath);
                    if (fileName.StartsWith("frame_") && int.TryParse(fileName.Substring(6), out int frameNum))
                    {
                        double timeCode = segment.StartTime + (frameNum - 1) * (1.0 / 30.0);
                        allFramePaths.Add((framePath, timeCode));
                    }
                }

                progress?.Report(30 + (segment.Index * 40 / segments.Count));
            }

            allFramePaths.Sort((a, b) => a.timeCode.CompareTo(b.timeCode));

            for (int i = 0; i < allFramePaths.Count; i++)
            {
                string newPath = Path.Combine(tempDir, $"frame_{i + 1:D4}.png");
                File.Copy(allFramePaths[i].path, newPath, true);

                if (i % 50 == 0)
                {
                    Debug.WriteLine($"Merged {i + 1}/{allFramePaths.Count} frames");
                }
            }

            foreach (var segment in segments)
            {
                CleanupTempDirectory(segment.TempDir);
            }

            Debug.WriteLine($"Merge complete: {allFramePaths.Count} frames total");
        }

        private string BuildSegmentExtractionArgs(string inputFile, VideoSegment segment, int fps, string scaleFilter, VideoInfo videoInfo)
        {
            string args = $"-ss {segment.StartTime:F3} -t {segment.Duration:F3} -i \"{inputFile}\"";
            args += " -vsync cfr";

            string videoFilters = $"fps={fps}";
            if (!string.IsNullOrEmpty(scaleFilter))
                videoFilters += $",{scaleFilter}";
            videoFilters += ",format=rgb24";

            args += $" -vf \"{videoFilters}\"";
            args += " -avoid_negative_ts make_zero";
            args += " -fflags +genpts";
            args += $" -start_number {segment.Index * 10000 + 1}";
            args += $" \"{Path.Combine(segment.TempDir, "frame_%08d.png")}\"";
            args += " -y";

            return args;
        }

        private (int cols, int rows) CalculateOptimalLayout(int frameCount, System.Drawing.Size frameSize, string atlasMode)
        {
            const int MAX_DIMENSION = 16384;

            switch (atlasMode?.ToLower())
            {
                case "horizontal":
                    int maxCols = MAX_DIMENSION / frameSize.Width;
                    int cols = Math.Min(frameCount, maxCols);
                    int rows = (int)Math.Ceiling((double)frameCount / cols);
                    return (cols, rows);

                case "vertical":
                    int maxRows = MAX_DIMENSION / frameSize.Height;
                    int vRows = Math.Min(frameCount, maxRows);
                    int vCols = (int)Math.Ceiling((double)frameCount / vRows);
                    return (vCols, vRows);

                case "grid":
                default:
                    int gridCols = (int)Math.Ceiling(Math.Sqrt(frameCount));
                    int gridRows = (int)Math.Ceiling((double)frameCount / gridCols);

                    while (gridCols * frameSize.Width > MAX_DIMENSION && gridCols > 1)
                    {
                        gridCols--;
                        gridRows = (int)Math.Ceiling((double)frameCount / gridCols);
                    }

                    while (gridRows * frameSize.Height > MAX_DIMENSION && gridRows > 1)
                    {
                        gridRows--;
                        gridCols = (int)Math.Ceiling((double)frameCount / gridRows);
                    }

                    return (gridCols, gridRows);
            }
        }

        private async Task<Process> ExtractFramesWithTimeout(string arguments, TimeSpan timeout, IProgress<int> progress)
        {
            var psi = new ProcessStartInfo
            {
                FileName = _ffmpegPath,
                Arguments = arguments,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            var process = Process.Start(psi);
            if (process == null)
                throw new InvalidOperationException("Could not start FFmpeg");

            var outputLines = new List<string>();
            var errorLines = new List<string>();
            var lastProgressTime = DateTime.Now;
            var lastFrameCount = 0;

            var errorTask = Task.Run(async () =>
            {
                try
                {
                    using var reader = process.StandardError;
                    string line;
                    while ((line = await reader.ReadLineAsync()) != null)
                    {
                        errorLines.Add(line);

                        if (line.Contains("frame="))
                        {
                            var match = Regex.Match(line, @"frame=\s*(\d+)");
                            if (match.Success && int.TryParse(match.Groups[1].Value, out int frameNum))
                            {
                                if (frameNum > lastFrameCount)
                                {
                                    lastFrameCount = frameNum;
                                    lastProgressTime = DateTime.Now;
                                }

                                int progressPercent = Math.Min(100, 15 + (int)(frameNum * 0.85f));
                                progress?.Report(progressPercent);
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"Error reading stderr: {ex.Message}");
                }
            });

            var progressMonitorTask = Task.Run(async () =>
            {
                while (!process.HasExited)
                {
                    await Task.Delay(20000);

                    if (!process.HasExited && DateTime.Now - lastProgressTime > TimeSpan.FromMinutes(3))
                    {
                        Debug.WriteLine($"No progress detected for 3 minutes. Last frame: {lastFrameCount}");
                        throw new TimeoutException("The app appears to be stuck - no progress for 3 minutes");
                    }
                }
            });

            using var cts = new CancellationTokenSource(timeout);

            try
            {
                var completedTask = await Task.WhenAny(
                    process.WaitForExitAsync(cts.Token),
                    progressMonitorTask
                );

                if (completedTask == progressMonitorTask)
                {
                    await progressMonitorTask;
                }

                await errorTask;
            }
            catch (OperationCanceledException)
            {
                try
                {
                    if (!process.HasExited)
                    {
                        process.Kill();
                        process.WaitForExit(2000);
                    }
                }
                catch { }

                throw new TimeoutException($"The app took longer than {timeout.TotalMinutes} minutes to process video");
            }

            if (process.ExitCode != 0)
            {
                string errorMsg = "FFmpeg error:\n";

                var relevantErrors = errorLines
                    .Where(line =>
                        line.Contains("Error") ||
                        line.Contains("Invalid") ||
                        line.Contains("Failed") ||
                        line.Contains("No such file") ||
                        line.Contains("Permission denied") ||
                        line.Contains("Unsupported") ||
                        line.Contains("Cannot determine") ||
                        line.Contains("Conversion failed"))
                    .TakeLast(3);

                if (relevantErrors.Any())
                {
                    errorMsg += string.Join("\n", relevantErrors);
                }
                else if (errorLines.Count > 0)
                {
                    errorMsg += string.Join("\n", errorLines.TakeLast(2));
                }
                else
                {
                    errorMsg += $"Exit code: {process.ExitCode}";
                }

                throw new InvalidOperationException(errorMsg);
            }

            return process;
        }


        private void ValidateVideoForAtlas(VideoInfo videoInfo, int fps)
        {
            int estimatedFrames = (int)Math.Ceiling(videoInfo.Duration * fps);
            long bytesPerFrame = videoInfo.Width * videoInfo.Height * 4L;
            long estimatedMemory = bytesPerFrame * estimatedFrames;

            const long MAX_ATLAS_MEMORY = 500L * 1024 * 1024;
            const int MAX_FRAMES = 1000;
            const int MAX_DIMENSION = 8192;
            const int MIN_DIMENSION = 16;
            const int RECOMMENDED_MAX = 3840;

            if (videoInfo.Width > MAX_DIMENSION || videoInfo.Height > MAX_DIMENSION)
            {
                throw new InvalidOperationException(
                    $"Resolution too high: {videoInfo.Width}x{videoInfo.Height}\n" +
                    $"Maximum supported resolution: {MAX_DIMENSION}x{MAX_DIMENSION}\n" +
                    $"Recommended: Scale down to 4K ({RECOMMENDED_MAX}x{RECOMMENDED_MAX * videoInfo.Height / videoInfo.Width}) or lower.");
            }

            if (videoInfo.Width < MIN_DIMENSION || videoInfo.Height < MIN_DIMENSION)
            {
                throw new InvalidOperationException(
                    $"Resolution too low: {videoInfo.Width}x{videoInfo.Height}\n" +
                    $"Minimum supported resolution: {MIN_DIMENSION}x{MIN_DIMENSION}\n" +
                    $"The video may not process correctly at this size.");
            }

            double aspectRatio = (double)videoInfo.Width / videoInfo.Height;
            const double MAX_ASPECT_RATIO = 10.0;
            const double MIN_ASPECT_RATIO = 0.1;

            if (aspectRatio > MAX_ASPECT_RATIO || aspectRatio < MIN_ASPECT_RATIO)
            {
                throw new InvalidOperationException(
                    $"Extreme aspect ratio detected: {aspectRatio:F2}:1\n" +
                    $"Supported range: {MIN_ASPECT_RATIO}:1 to {MAX_ASPECT_RATIO}:1\n" +
                    $"Very wide or tall videos may cause processing issues.\n" +
                    $"Consider cropping or resizing to a more standard aspect ratio (e.g., 16:9, 4:3, 1:1).");
            }

            if (estimatedMemory > MAX_ATLAS_MEMORY)
            {
                throw new InvalidOperationException(
                    $"Video is too large to create sprite atlas.\n" +
                    $"Estimated memory: {estimatedMemory / (1024 * 1024)}MB (maximum: {MAX_ATLAS_MEMORY / (1024 * 1024)}MB)\n" +
                    $"Solutions:\n" +
                    $"- Reduce atlas FPS (current: {fps})\n" +
                    $"- Lower the video resolution\n" +
                    $"- Lower the output resolution of the sprite atlas\n" +
                    $"- Cut video to shorter duration (5, 10 or 30 seconds)");
            }

            if (estimatedFrames > MAX_FRAMES)
            {
                throw new InvalidOperationException(
                    $"Too many frames estimated: {estimatedFrames} (maximum: {MAX_FRAMES})\n" +
                    $"Duration: {videoInfo.Duration:F1}s, Atlas FPS: {fps}\n" +
                    $"Reduce atlas FPS or video duration.");
            }

            if (videoInfo.Duration > 30)
            {
                throw new InvalidOperationException(
                    $"Video too long: {videoInfo.Duration:F1}s (maximum: 30s)\n" +
                    $"Very long videos may cause infinite timeouts or memory issues.\n" +
                    $"Cut video to shorter duration (5, 10 or 30 seconds)");
            }
        }

        private string BuildVFRCompatibleArgs(string inputFile, string tempDir, int fps, string scaleFilter, VideoInfo videoInfo)
        {
            string baseArgs = $"-i \"{inputFile}\"";
            baseArgs += " -vsync cfr";
            double maxDuration = Math.Min(videoInfo.Duration, 30.0);
            baseArgs += $" -t {maxDuration:F2}";
            string videoFilters = $"fps={fps}";

            if (!string.IsNullOrEmpty(scaleFilter))
            {
                videoFilters += $",{scaleFilter}";
            }

            videoFilters += ",format=rgb24";
            baseArgs += $" -vf \"{videoFilters}\"";
            baseArgs += " -avoid_negative_ts make_zero";
            baseArgs += " -fflags +genpts";
            baseArgs += " -start_number 1";
            baseArgs += $" \"{Path.Combine(tempDir, "frame_%04d.png")}\"";
            baseArgs += " -y";

            return baseArgs;
        }

        private void CleanupTempDirectory(string tempDir)
        {
            if (!Directory.Exists(tempDir)) return;

            try
            {
                var files = Directory.GetFiles(tempDir);
                foreach (var file in files)
                {
                    try
                    {
                        File.SetAttributes(file, FileAttributes.Normal);
                        File.Delete(file);
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"Could not be deleted {file}: {ex.Message}");
                    }
                }

                Directory.Delete(tempDir, true);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error cleaning temporary directory: {ex.Message}");

                try
                {
                    var files = Directory.GetFiles(tempDir);
                    foreach (var file in files)
                    {
                        try
                        {
                            File.Delete(file);
                        }
                        catch { }
                    }
                }
                catch { }
            }
        }

        private (int col, int row) GetFramePosition(int frameIndex, int totalCols, int totalRows, string atlasMode)
        {
            if (string.IsNullOrEmpty(atlasMode))
                atlasMode = "Grid";

            switch (atlasMode.ToLower())
            {
                case "horizontal":
                    int col = frameIndex % totalCols;
                    int row = frameIndex / totalCols;
                    return (col, row);

                case "vertical":
                    int colVert = frameIndex / totalRows;
                    int rowVert = frameIndex % totalRows;
                    return (colVert, rowVert);

                case "grid":
                default:
                    int colGrid = frameIndex % totalCols;
                    int rowGrid = frameIndex / totalCols;
                    return (colGrid, rowGrid);
            }
        }

        public async Task ConvertAsync(string inputFile, string outputFile, string arguments, double totalSeconds, IProgress<int> progress)
        {
            if (_disposed)
                throw new ObjectDisposedException(nameof(VideoConversionService));

            System.Diagnostics.Debug.WriteLine($"FFmpeg Arguments: {arguments}");
            System.Diagnostics.Debug.WriteLine($"Input: {inputFile}");
            System.Diagnostics.Debug.WriteLine($"Output: {outputFile}");

            using var cancellationTokenSource = new CancellationTokenSource();
            var cancellationToken = cancellationTokenSource.Token;

            var psi = new ProcessStartInfo
            {
                FileName = _ffmpegPath,
                Arguments = arguments,
                RedirectStandardError = true,
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            _currentProcess = Process.Start(psi);
            if (_currentProcess == null)
                throw new InvalidOperationException("Failed to start FFmpeg process");

            try
            {
                var timeRegex = new Regex(@"time=(\d+):(\d+):(\d+(?:\.\d+)?)", RegexOptions.Compiled);
                var lastProgress = 0;
                var progressLock = new object();

                var stderrTask = Task.Run(async () =>
                {
                    try
                    {
                        using var reader = _currentProcess.StandardError;
                        string? line;

                        while ((line = await reader.ReadLineAsync()) != null)
                        {
                            cancellationToken.ThrowIfCancellationRequested();

                            if (outputFile.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase))
                            {
                                System.Diagnostics.Debug.WriteLine($"FFmpeg: {line}");
                            }

                            if (string.IsNullOrEmpty(line)) continue;

                            var match = timeRegex.Match(line);
                            if (match.Success)
                            {
                                try
                                {
                                    double hours = double.Parse(match.Groups[1].Value);
                                    double minutes = double.Parse(match.Groups[2].Value);
                                    double seconds = double.Parse(match.Groups[3].Value);

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
                        System.Diagnostics.Debug.WriteLine($"Error reading FFmpeg stderr: {ex.Message}");
                    }
                }, cancellationToken);

                var stdoutTask = Task.Run(async () =>
                {
                    try
                    {
                        using var reader = _currentProcess.StandardOutput;
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
                    await _currentProcess.WaitForExitAsync(cancellationToken);
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

                if (outputFile.EndsWith(".mp4", StringComparison.OrdinalIgnoreCase))
                {
                    System.Diagnostics.Debug.WriteLine($"FFmpeg Exit Code: {_currentProcess.ExitCode}");
                }

                if (_currentProcess.ExitCode != 0)
                {
                    throw new InvalidOperationException($"Conversion failed with exit code {_currentProcess.ExitCode}");
                }

                if (!File.Exists(outputFile))
                {
                    throw new InvalidOperationException("Output file was not created");
                }

                var fileInfo = new FileInfo(outputFile);
                if (fileInfo.Length == 0)
                {
                    File.Delete(outputFile);
                    throw new InvalidOperationException("Output file is empty - conversion may have failed");
                }

                progress?.Report(100);
            }
            catch (OperationCanceledException)
            {
                if (File.Exists(outputFile))
                {
                    try { File.Delete(outputFile); } catch { }
                }
                throw;
            }
            catch (Exception)
            {
                if (File.Exists(outputFile))
                {
                    try { File.Delete(outputFile); } catch { }
                }
                throw;
            }
            finally
            {
                try
                {
                    if (_currentProcess != null && !_currentProcess.HasExited)
                    {
                        _currentProcess.Kill();
                    }
                }
                catch
                {

                }
                finally
                {
                    _currentProcess?.Dispose();
                    _currentProcess = null;
                }
            }
        }

        public void CancelCurrentConversion()
        {
            try
            {
                if (_currentProcess != null && !_currentProcess.HasExited)
                {
                    _currentProcess.CloseMainWindow();

                    if (!_currentProcess.WaitForExit(2000))
                    {
                        _currentProcess.Kill();
                        _currentProcess.WaitForExit(1000);
                    }
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error cancelling conversion: {ex.Message}");
            }
            finally
            {
                try
                {
                    _currentProcess?.Dispose();
                }
                catch { }
                _currentProcess = null;
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
