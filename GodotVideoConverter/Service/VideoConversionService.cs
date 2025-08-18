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

        public async Task ConvertToSpriteAtlasAsync(string inputFile, string outputFile, int fps, string scaleFilter, string atlasMode, IProgress<int> progress)
        {
            string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            Directory.CreateDirectory(tempDir);

            Process? extractProcess = null;

            try
            {
                progress?.Report(5);

                var videoInfo = await GetVideoInfoAsync(inputFile);
                if (!videoInfo.IsValid)
                {
                    throw new InvalidOperationException("Video file is not valid");
                }

                progress?.Report(10);

                ValidateVideoForAtlas(videoInfo, fps);

                string frameExtractArgs = BuildVFRCompatibleArgs(inputFile, tempDir, fps, scaleFilter, videoInfo);

                progress?.Report(15);

                extractProcess = await ExtractFramesWithTimeout(frameExtractArgs, TimeSpan.FromMinutes(5), progress);

                progress?.Report(60);

                var frameFiles = Directory.GetFiles(tempDir, "frame_*.png");
                if (frameFiles.Length == 0)
                {
                    throw new InvalidOperationException("Could not extract frames from video. Video might be corrupted or have unsupported format.");
                }

                Array.Sort(frameFiles, (x, y) => string.Compare(Path.GetFileName(x), Path.GetFileName(y)));

                progress?.Report(70);

                await CreateOptimizedAtlas(frameFiles, outputFile, atlasMode, progress);

                progress?.Report(100);
            }
            catch (TimeoutException)
            {
                throw new InvalidOperationException("Frame extraction took too long. Video might be too complex or have format issues.");
            }
            catch (Exception ex)
            {
                throw new InvalidOperationException($"Error creating sprite atlas: {ex.Message}");
            }
            finally
            {
                try
                {
                    if (extractProcess != null && !extractProcess.HasExited)
                    {
                        extractProcess.Kill();
                        extractProcess.WaitForExit(2000);
                    }
                }
                catch { }

                extractProcess?.Dispose();
                CleanupTempDirectory(tempDir);
            }
        }

        private async Task CreateOptimizedAtlas(string[] frameFiles, string outputFile, string atlasMode, IProgress<int> progress)
        {
            if (frameFiles.Length == 0)
                throw new InvalidOperationException("No frames to process");

            System.Drawing.Size frameSize;
            using (var firstFrame = System.Drawing.Image.FromFile(frameFiles[0]))
            {
                frameSize = firstFrame.Size;
            }

            var layout = CalculateOptimalLayout(frameFiles.Length, frameSize, atlasMode);

            progress?.Report(75);

            long totalWidth = (long)frameSize.Width * layout.cols;
            long totalHeight = (long)frameSize.Height * layout.rows;

            const int MAX_SIZE = 16384;
            if (totalWidth > MAX_SIZE || totalHeight > MAX_SIZE)
            {
                throw new InvalidOperationException(
                    $"Atlas too large: {totalWidth}x{totalHeight} (maximum: {MAX_SIZE}x{MAX_SIZE})\n" +
                    $"Frames: {frameFiles.Length}, Layout: {layout.cols}x{layout.rows}");
            }

            progress?.Report(80);

            try
            {
                using var atlas = new System.Drawing.Bitmap((int)totalWidth, (int)totalHeight,
                    System.Drawing.Imaging.PixelFormat.Format32bppArgb);
                using var graphics = System.Drawing.Graphics.FromImage(atlas);

                graphics.Clear(System.Drawing.Color.Transparent);
                graphics.CompositingMode = System.Drawing.Drawing2D.CompositingMode.SourceCopy;
                graphics.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.NearestNeighbor;

                for (int i = 0; i < frameFiles.Length; i++)
                {
                    var pos = GetFramePosition(i, layout.cols, layout.rows, atlasMode);
                    int x = pos.col * frameSize.Width;
                    int y = pos.row * frameSize.Height;

                    using var frame = System.Drawing.Image.FromFile(frameFiles[i]);
                    graphics.DrawImage(frame, x, y, frameSize.Width, frameSize.Height);

                    if (i % 5 == 0)
                    {
                        int progressPercent = 80 + (int)((i + 1) * 19.0 / frameFiles.Length);
                        progress?.Report(progressPercent);
                    }
                }

                atlas.Save(outputFile, System.Drawing.Imaging.ImageFormat.Png);

                progress?.Report(99);
            }
            catch (OutOfMemoryException)
            {
                throw new InvalidOperationException(
                    "Insufficient memory to create atlas.\n" +
                    "Reduce video resolution, FPS or duration.");
            }
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
                                int progressPercent = Math.Min(59, 15 + (frameNum * 44 / 100));
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

            using var cts = new CancellationTokenSource(timeout);

            try
            {
                await process.WaitForExitAsync(cts.Token);
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

                throw new TimeoutException($"FFmpeg took longer than {timeout.TotalMinutes} minutes to process video");
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
                        line.Contains("Unsupported"))
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

            const long MAX_ATLAS_MEMORY = 200L * 1024 * 1024;
            const int MAX_FRAMES = 500;
            const int MAX_DIMENSION = 8192;

            if (estimatedMemory > MAX_ATLAS_MEMORY)
            {
                throw new InvalidOperationException(
                    $"Video is too large to create sprite atlas.\n" +
                    $"Estimated memory: {estimatedMemory / (1024 * 1024)}MB (maximum: {MAX_ATLAS_MEMORY / (1024 * 1024)}MB)\n" +
                    $"Solutions:\n" +
                    $"- Reduce atlas FPS (current: {fps})\n" +
                    $"- Use lower resolution\n" +
                    $"- Cut video to shorter duration");
            }

            if (estimatedFrames > MAX_FRAMES)
            {
                throw new InvalidOperationException(
                    $"Too many frames estimated: {estimatedFrames} (maximum: {MAX_FRAMES})\n" +
                    $"Duration: {videoInfo.Duration:F1}s, Atlas FPS: {fps}\n" +
                    $"Reduce atlas FPS or video duration.");
            }

            if (videoInfo.Width > MAX_DIMENSION || videoInfo.Height > MAX_DIMENSION)
            {
                throw new InvalidOperationException(
                    $"Resolution too high: {videoInfo.Width}x{videoInfo.Height}\n" +
                    $"Maximum: {MAX_DIMENSION}x{MAX_DIMENSION}\n" +
                    $"Use scale filter to reduce resolution.");
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
                        System.Diagnostics.Debug.WriteLine($"No se pudo eliminar {file}: {ex.Message}");
                    }
                }

                Directory.Delete(tempDir, true);
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"Error limpiando directorio temporal: {ex.Message}");

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

                var timeoutTask = Task.Delay(TimeSpan.FromMinutes(30), cancellationToken);
                var completedTask = await Task.WhenAny(processTask, timeoutTask);

                if (completedTask == timeoutTask)
                {
                    throw new TimeoutException("FFmpeg conversion timed out after 30 minutes");
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
                    throw new InvalidOperationException($"FFmpeg conversion failed with exit code {_currentProcess.ExitCode}");
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
