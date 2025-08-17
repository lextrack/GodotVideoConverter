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

        // Método principal actualizado con validaciones de tamaño
        public async Task ConvertToSpriteAtlasAsync(string inputFile, string outputFile, int fps, string scaleFilter, string atlasMode, IProgress<int> progress)
        {
            string tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
            Directory.CreateDirectory(tempDir);

            try
            {
                // Extraer frames del video
                string frameExtractArgs = $"-i \"{inputFile}\" -vf \"fps={fps}";
                if (!string.IsNullOrEmpty(scaleFilter))
                {
                    frameExtractArgs += $",{scaleFilter}";
                }
                frameExtractArgs += $"\" \"{Path.Combine(tempDir, "frame_%04d.png")}\"";

                var frameExtractPsi = new ProcessStartInfo
                {
                    FileName = _ffmpegPath,
                    Arguments = frameExtractArgs,
                    RedirectStandardError = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };

                using var extractProcess = Process.Start(frameExtractPsi);
                if (extractProcess == null) return;

                await extractProcess.WaitForExitAsync();

                // Obtener archivos de frames ordenados
                var frameFiles = Directory.GetFiles(tempDir, "frame_*.png");
                Array.Sort(frameFiles, (x, y) => string.Compare(Path.GetFileName(x), Path.GetFileName(y)));

                if (frameFiles.Length == 0) return;

                // Cargar el primer frame para obtener dimensiones
                using var firstFrame = System.Drawing.Image.FromFile(frameFiles[0]);
                int frameWidth = firstFrame.Width;
                int frameHeight = firstFrame.Height;

                // Calcular layout según el modo seleccionado con validaciones
                var layoutInfo = CalculateAtlasLayout(frameFiles.Length, atlasMode, frameWidth, frameHeight);
                int cols = layoutInfo.cols;
                int rows = layoutInfo.rows;

                // Validar que las dimensiones no excedan los límites
                long totalWidth = (long)frameWidth * cols;
                long totalHeight = (long)frameHeight * rows;

                // Límites de GDI+ (aproximadamente 65535 píxeles en cualquier dimensión)
                const int MAX_DIMENSION = 32767; // Usar un límite más conservador

                if (totalWidth > MAX_DIMENSION || totalHeight > MAX_DIMENSION)
                {
                    throw new InvalidOperationException($"El atlas resultante sería demasiado grande ({totalWidth}x{totalHeight}). " +
                                                      $"Límite máximo: {MAX_DIMENSION} píxeles por dimensión. " +
                                                      "Considera usar menos frames, menor resolución, o modo Grid.");
                }

                // Crear el atlas
                using var atlas = new System.Drawing.Bitmap((int)totalWidth, (int)totalHeight);
                using var graphics = System.Drawing.Graphics.FromImage(atlas);
                graphics.Clear(System.Drawing.Color.Transparent);

                // Colocar cada frame en su posición
                for (int i = 0; i < frameFiles.Length; i++)
                {
                    var position = GetFramePosition(i, cols, rows, atlasMode);
                    int col = position.col;
                    int row = position.row;

                    using var frame = System.Drawing.Image.FromFile(frameFiles[i]);
                    graphics.DrawImage(frame, col * frameWidth, row * frameHeight);

                    // Reportar progreso
                    progress?.Report((int)((i + 1) * 100.0 / frameFiles.Length));
                }

                // Guardar el atlas
                atlas.Save(outputFile, System.Drawing.Imaging.ImageFormat.Png);
            }
            finally
            {
                // Limpiar archivos temporales
                if (Directory.Exists(tempDir))
                {
                    try
                    {
                        Directory.Delete(tempDir, true);
                    }
                    catch
                    {
                        // Ignorar errores de limpieza
                    }
                }
            }
        }

        // Método auxiliar para calcular el layout del atlas CON VALIDACIONES
        private (int cols, int rows) CalculateAtlasLayout(int frameCount, string atlasMode, int frameWidth, int frameHeight)
        {
            if (string.IsNullOrEmpty(atlasMode))
                atlasMode = "Grid";

            const int MAX_DIMENSION = 32767; // Límite conservador para GDI+

            switch (atlasMode.ToLower())
            {
                case "horizontal":
                    // Limitar el número de columnas para evitar atlas demasiado anchos
                    int maxCols = MAX_DIMENSION / frameWidth;
                    if (frameCount <= maxCols)
                    {
                        return (frameCount, 1);  // Una sola fila si cabe
                    }
                    else
                    {
                        // Si hay demasiados frames, crear múltiples filas
                        int cols = maxCols;
                        int rows = (int)Math.Ceiling((double)frameCount / cols);
                        return (cols, rows);
                    }

                case "vertical":
                    // Limitar el número de filas para evitar atlas demasiado altos
                    int maxRows = MAX_DIMENSION / frameHeight;
                    if (frameCount <= maxRows)
                    {
                        return (1, frameCount);  // Una sola columna si cabe
                    }
                    else
                    {
                        // Si hay demasiados frames, crear múltiples columnas
                        int rows = maxRows;
                        int cols = (int)Math.Ceiling((double)frameCount / rows);
                        return (cols, rows);
                    }

                case "grid":
                default:
                    // Modo grid: crear una cuadrícula lo más cuadrada posible
                    int gridCols = (int)Math.Ceiling(Math.Sqrt(frameCount));
                    int gridRows = (int)Math.Ceiling((double)frameCount / gridCols);

                    // Verificar que no exceda los límites
                    if (gridCols * frameWidth > MAX_DIMENSION || gridRows * frameHeight > MAX_DIMENSION)
                    {
                        // Recalcular con límites más estrictos
                        int maxGridCols = MAX_DIMENSION / frameWidth;
                        int maxGridRows = MAX_DIMENSION / frameHeight;

                        gridCols = Math.Min(gridCols, maxGridCols);
                        gridRows = (int)Math.Ceiling((double)frameCount / gridCols);

                        if (gridRows > maxGridRows)
                        {
                            gridRows = maxGridRows;
                            gridCols = (int)Math.Ceiling((double)frameCount / gridRows);
                        }
                    }

                    return (gridCols, gridRows);
            }
        }

        // Método auxiliar para obtener la posición de cada frame (sin cambios)
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
                    // Distribución en grilla: de izquierda a derecha, de arriba hacia abajo
                    int colGrid = frameIndex % totalCols;
                    int rowGrid = frameIndex / totalCols;
                    return (colGrid, rowGrid);
            }
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
