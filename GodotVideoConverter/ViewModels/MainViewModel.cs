using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using GodotVideoConverter.Models;
using GodotVideoConverter.Services;
using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Threading;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel : ObservableObject, IDisposable
    {
        private readonly VideoConversionService _service;
        private readonly VideoRecommendationService _recommendationService;
        private bool _isInitialized = false;
        private DispatcherTimer? _saveTimer;

        [ObservableProperty] private bool isConverting = false;
        [ObservableProperty] private string? selectedFormat;
        [ObservableProperty] private string? selectedResolution;
        [ObservableProperty] private string? selectedQuality;
        [ObservableProperty] private string? selectedOgvMode;
        [ObservableProperty] private bool keepAudio;
        [ObservableProperty] private string? fps;
        [ObservableProperty] private int progress;
        [ObservableProperty] private string statusMessage = "Drag the files to the box to convert them";
        [ObservableProperty] private string outputFolder;
        [ObservableProperty] private bool isOgvModeEnabled;
        [ObservableProperty] private string videoInfo = "";
        [ObservableProperty] private string recommendations = "";
        [ObservableProperty] private int selectedFileIndex = -1;
        [ObservableProperty] private int atlasFps = 10;
        [ObservableProperty] private string? selectedAtlasMode = "Grid";
        [ObservableProperty] private string? selectedAtlasResolution = "Keep Original";
        [ObservableProperty] private bool keepOriginalAtlasResolution = true;
        [ObservableProperty] private bool isGeneratingAtlas = false;

        public void Dispose()
        {
            _service.Dispose();
            _saveTimer?.Stop();
        }

        [RelayCommand]
        public void CancelConversion()
        {
            if (IsConverting)
            {
                _service.CancelCurrentConversion();
                IsConverting = false;
                StatusMessage = "Conversion cancelled by user";
            }
        }

        public ObservableCollection<string> InputFiles { get; } = new();
        public ObservableCollection<VideoInfo> VideoDetails { get; } = new();

        public ObservableCollection<string> Formats { get; } = new()
        {
            "OGV (Godot 4.x)", "MP4 (H.264/AAC)", "WebM (VP9/Opus)"
        };

        public ObservableCollection<string> Resolutions { get; } = new()
        {
            "3840x2160", "1920x1080", "1366x768", "1280x720", "1280x960", "1024x768", "854x480", "800x600", "640x360", "640x480", "512x512", "480x270", "426x240", "384x216", "256x256", "Keep original"
        };

        public ObservableCollection<string> AtlasResolutions { get; } = new()
        {
            "Low",
            "Medium",
            "High",
            "Very High",
            "Keep Original"
        };

        private string GetAtlasResolutionValue(string selectedResolution)
        {
            return selectedResolution switch
            {
                "Low" => "64x64",
                "Medium" => "128x128",
                "High" => "256x256",
                "Very High" => "512x512",
                _ => ""
            };
        }

        public ObservableCollection<string> Qualities { get; } = new()
        {
            "Ultra", "High", "Balanced", "Optimized", "Tiny"
        };

        public ObservableCollection<string> OgvModes { get; } = new()
        {
            "Standard", "Constant FPS (CFR)", "Optimized for weak hardware", "Ideal Loop", "Streaming Optimized", "Mobile Optimized"
        };

        public ObservableCollection<string> AtlasModes { get; } = new()
        {
            "Grid", "Horizontal", "Vertical"
        };

        public MainViewModel()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            _service = new VideoConversionService(baseDir);
            _recommendationService = new VideoRecommendationService();

            _saveTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(500)
            };
            _saveTimer.Tick += (s, e) =>
            {
                _saveTimer.Stop();
                SaveSettings();
            };

            LoadSettings();
            UpdateOgvModeAvailability();
            _isInitialized = true;
        }

        private async Task ConvertToSpriteAtlasAsync(string inputFile, string outputFolder, string fileName)
        {
            string outFile = Path.Combine(outputFolder, $"{fileName}_atlas.png");
            int counter = 1;
            while (File.Exists(outFile))
            {
                outFile = Path.Combine(outputFolder, $"{fileName}_atlas_{counter}.png");
                counter++;
            }

            string scaleFilter = "";
            if (!string.IsNullOrEmpty(SelectedAtlasResolution) &&
                SelectedAtlasResolution != "Keep Original")
            {
                string resolutionValue = GetAtlasResolutionValue(SelectedAtlasResolution);
                var parts = resolutionValue.Split('x');
                if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                {
                    scaleFilter = $"scale={w}:{h}:force_original_aspect_ratio=decrease";
                }
            }

            var progressHandler = new Progress<int>(p => Progress = p);

            string atlasMode = SelectedAtlasMode ?? "Grid";

            await _service.ConvertToSpriteAtlasAsync(inputFile, outFile, AtlasFps, scaleFilter, atlasMode, progressHandler);
        }

        private void LoadSettings()
        {
            try
            {
                OutputFolder = Properties.Settings.Default.OutputFolder;
                SelectedFormat = Properties.Settings.Default.SelectedFormat;
                SelectedResolution = Properties.Settings.Default.SelectedResolution;
                SelectedQuality = Properties.Settings.Default.SelectedQuality;
                SelectedOgvMode = Properties.Settings.Default.SelectedOgvMode;
                KeepAudio = Properties.Settings.Default.KeepAudio;
                Fps = Properties.Settings.Default.Fps;

                if (string.IsNullOrEmpty(OutputFolder))
                {
                    OutputFolder = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "output");
                }
                if (string.IsNullOrEmpty(SelectedFormat))
                {
                    SelectedFormat = "OGV (Godot 4.x)";
                }
                if (string.IsNullOrEmpty(SelectedResolution))
                {
                    SelectedResolution = "Keep original";
                }
                if (string.IsNullOrEmpty(SelectedQuality))
                {
                    SelectedQuality = "Optimized";
                }
                if (string.IsNullOrEmpty(SelectedOgvMode))
                {
                    SelectedOgvMode = "Standard";
                }
                if (string.IsNullOrEmpty(Fps) || !double.TryParse(Fps, out _))
                {
                    Fps = "30";
                }
            }
            catch
            {
                SetDefaultValues();
            }
        }

        private void SetDefaultValues()
        {
            OutputFolder = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "output");
            SelectedFormat = "OGV (Godot 4.x)";
            SelectedResolution = "Keep original";
            SelectedQuality = "Optimized";
            SelectedOgvMode = "Standard";
            Fps = "30";
            KeepAudio = false;
        }

        private void SaveSettingsDelayed()
        {
            if (!_isInitialized) return;
            _saveTimer?.Stop();
            _saveTimer?.Start();
        }

        private void SaveSettings()
        {
            try
            {
                Properties.Settings.Default.OutputFolder = OutputFolder;
                Properties.Settings.Default.SelectedFormat = SelectedFormat ?? "";
                Properties.Settings.Default.SelectedResolution = SelectedResolution ?? "";
                Properties.Settings.Default.SelectedQuality = SelectedQuality ?? "";
                Properties.Settings.Default.SelectedOgvMode = SelectedOgvMode ?? "";
                Properties.Settings.Default.KeepAudio = KeepAudio;
                Properties.Settings.Default.Fps = Fps ?? "";
                Properties.Settings.Default.Save();
            }
            catch { }
        }

        partial void OnSelectedFormatChanged(string? value)
        {
            UpdateOgvModeAvailability();
            SaveSettingsDelayed();
        }

        partial void OnSelectedResolutionChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnSelectedQualityChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnSelectedOgvModeChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnKeepAudioChanged(bool value)
        {
            SaveSettingsDelayed();
        }

        partial void OnFpsChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnOutputFolderChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnSelectedFileIndexChanged(int value)
        {
            UpdateSelectedVideoInfo();
        }

        private void UpdateOgvModeAvailability()
        {
            bool shouldBeEnabled = !string.IsNullOrEmpty(SelectedFormat) &&
                                 SelectedFormat.StartsWith("OGV", StringComparison.OrdinalIgnoreCase);
            IsOgvModeEnabled = shouldBeEnabled;

            if (!IsOgvModeEnabled && _isInitialized && SelectedOgvMode != "Standard")
            {
                SelectedOgvMode = "Standard";
            }
        }

        private async Task UpdateVideoInfoAsync()
        {
            if (InputFiles.Count == 0)
            {
                VideoInfo = "";
                Recommendations = "";
                return;
            }

            try
            {
                VideoDetails.Clear();

                foreach (var file in InputFiles)
                {
                    var info = await _service.GetVideoInfoAsync(file);
                    VideoDetails.Add(info);
                }

                if (SelectedFileIndex >= 0 && SelectedFileIndex < VideoDetails.Count)
                {
                    UpdateSelectedVideoInfo();
                }
                else if (VideoDetails.Count > 0)
                {
                    SelectedFileIndex = 0;
                }
            }
            catch (Exception ex)
            {
                VideoInfo = $"Error analyzing video: {ex.Message}";
                Recommendations = "";
            }
        }

        private void UpdateSelectedVideoInfo()
        {
            if (SelectedFileIndex < 0 || SelectedFileIndex >= VideoDetails.Count)
            {
                VideoInfo = "";
                Recommendations = "";
                return;
            }

            var selectedVideo = VideoDetails[SelectedFileIndex];
            var fileName = Path.GetFileName(InputFiles[SelectedFileIndex]);

            if (selectedVideo.IsValid)
            {
                VideoInfo = $"{fileName}\nResolution: {selectedVideo.Resolution} | FPS: {selectedVideo.FrameRate:F1} | Duration: {selectedVideo.Duration:F1}s | Codec: {selectedVideo.VideoCodec}";
                if (selectedVideo.HasAudio)
                {
                    VideoInfo += $" | Audio: {selectedVideo.AudioCodec}";
                }

                Recommendations = _recommendationService.GetGodotRecommendations(selectedVideo, KeepAudio);
            }
        }

        [RelayCommand]
        public void BrowseOutputFolder()
        {
            var dialog = new OpenFolderDialog()
            {
                Title = "Select output folder for converted videos",
                InitialDirectory = OutputFolder
            };

            if (dialog.ShowDialog() == true)
            {
                OutputFolder = dialog.FolderName;
                StatusMessage = $"Output folder set to: {OutputFolder}";
            }
        }

        [RelayCommand]
        public void ClearList()
        {
            InputFiles.Clear();
            VideoDetails.Clear();
            VideoInfo = "";
            Recommendations = "";
            StatusMessage = "List cleared. Drag files here to convert";
            Progress = 0;
        }

        [RelayCommand]
        public async Task AddFilesAsync(IEnumerable<string> files)
        {
            var videoFiles = new List<string>();

            foreach (var file in files)
            {
                if (File.Exists(file))
                {
                    var isValid = await _service.ValidateVideoFileAsync(file);
                    if (isValid)
                    {
                        videoFiles.Add(file);
                        if (!InputFiles.Contains(file))
                        {
                            InputFiles.Add(file);
                        }
                    }
                    else
                    {
                        StatusMessage = $"Invalid video file or ffmpeg and its resources are not found in the root folder";
                    }
                }
            }

            if (videoFiles.Count > 0)
            {
                StatusMessage = $"Added {videoFiles.Count} video file(s)";
                await UpdateVideoInfoAsync();
            }
        }

        [RelayCommand]
        public void OpenOutputFolder()
        {
            Directory.CreateDirectory(OutputFolder);

            try
            {
                System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo()
                {
                    FileName = OutputFolder,
                    UseShellExecute = true,
                    Verb = "open"
                });
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error opening output folder: {ex.Message}";
            }
        }

        private string GetFileExtension()
        {
            return SelectedFormat switch
            {
                "MP4 (H.264/AAC)" => ".mp4",
                "WebM (VP9/Opus)" => ".webm",
                _ => ".ogv"
            };
        }

        [RelayCommand]
        private async Task GenerateAtlasAsync()
        {
            if (InputFiles.Count == 0)
            {
                StatusMessage = "No files selected for atlas generation.";
                return;
            }

            IsGeneratingAtlas = true;

            try
            {
                Directory.CreateDirectory(OutputFolder);

                foreach (var file in InputFiles)
                {
                    string fileName = Path.GetFileNameWithoutExtension(file);
                    await ConvertToSpriteAtlasAsync(file, OutputFolder, fileName);
                    StatusMessage = $"Created sprite atlas: {fileName}_atlas.png";
                }

                StatusMessage = "All sprite atlases generated!";
            }
            finally
            {
                IsGeneratingAtlas = false;
            }
        }

        [RelayCommand]
        public async Task ConvertAsync()
        {
            if (InputFiles.Count == 0)
            {
                StatusMessage = "No files selected.";
                return;
            }

            if (!ValidateConversionParameters())
                return;

            IsConverting = true;
            Progress = 0;

            try
            {
                Directory.CreateDirectory(OutputFolder);

                int totalFiles = InputFiles.Count;
                for (int fileIndex = 0; fileIndex < InputFiles.Count; fileIndex++)
                {
                    var file = InputFiles[fileIndex];
                    string fileName = Path.GetFileNameWithoutExtension(file);

                    StatusMessage = $"Converting {fileName}... ({fileIndex + 1}/{totalFiles})";

                    try
                    {
                        double duration = await _service.GetVideoDurationAsync(file);
                        if (duration <= 0)
                        {
                            StatusMessage = $"Could not read duration of {fileName}";
                            continue;
                        }

                        var conversionParams = BuildConversionParameters(file, fileName);
                        if (conversionParams == null)
                        {
                            StatusMessage = $"Error building conversion parameters for {fileName}";
                            continue;
                        }

                        var progressHandler = new Progress<int>(p => {
                            int overallProgress = (int)((fileIndex * 100.0 + p) / totalFiles);
                            Progress = overallProgress;
                        });

                        await _service.ConvertAsync(
                            file,
                            conversionParams.OutputFile,
                            conversionParams.Arguments,
                            duration,
                            progressHandler);

                        StatusMessage = $"Converted: {Path.GetFileName(conversionParams.OutputFile)}";
                    }
                    catch (OperationCanceledException)
                    {
                        StatusMessage = "Conversion cancelled by user";
                        return;
                    }
                    catch (Exception ex)
                    {
                        StatusMessage = $"Error converting {fileName}: {ex.Message}";
                        continue;
                    }
                }

                Progress = 100;
                StatusMessage = "All conversions completed!";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Conversion error: {ex.Message}";
            }
            finally
            {
                IsConverting = false;
            }
        }

        private bool ValidateConversionParameters()
        {
            if (string.IsNullOrWhiteSpace(OutputFolder))
            {
                StatusMessage = "Please select an output folder";
                return false;
            }

            if (string.IsNullOrWhiteSpace(SelectedFormat))
            {
                StatusMessage = "Please select a format";
                return false;
            }

            if (!string.IsNullOrWhiteSpace(Fps))
            {
                if (!double.TryParse(Fps, out double fpsValue) || fpsValue <= 0 || fpsValue > 120)
                {
                    StatusMessage = "Please enter a valid FPS value (1-120)";
                    return false;
                }
            }

            return true;
        }

        private class ConversionParameters
        {
            public string OutputFile { get; set; } = "";
            public string Arguments { get; set; } = "";
        }

        private ConversionParameters? BuildConversionParameters(string inputFile, string fileName)
        {
            try
            {
                string extension = GetFileExtension();

                string outFileBase = Path.Combine(OutputFolder, fileName + "_converted" + extension);
                string outFile = outFileBase;
                int counter = 1;
                while (File.Exists(outFile))
                {
                    outFile = Path.Combine(OutputFolder, $"{fileName}_converted_{counter}{extension}");
                    counter++;
                }

                var (codecVideo, codecAudio, additionalArgs) = GetCodecParameters();

                string filterChain = BuildFilterChain();
                string filterArg = !string.IsNullOrEmpty(filterChain) ? $"-vf \"{filterChain}\"" : "";
                string args = $"-i \"{inputFile}\" {filterArg} {codecVideo} {codecAudio} {additionalArgs} \"{outFile}\"";

                return new ConversionParameters
                {
                    OutputFile = outFile,
                    Arguments = args
                };
            }
            catch (Exception ex)
            {
                StatusMessage = $"Error building parameters: {ex.Message}";
                return null;
            }
        }
        private (string codecVideo, string codecAudio, string additionalArgs) GetCodecParameters()
        {
            string codecVideo, codecAudio, additionalArgs;

            switch (SelectedFormat)
            {
                case "MP4 (H.264/AAC)":
                    codecVideo = SelectedQuality switch
                    {
                        "Ultra" => "-c:v libx264 -crf 15 -preset slower -profile:v high -level 4.1",
                        "High" => "-c:v libx264 -crf 18 -preset slow -profile:v high -level 4.1",
                        "Balanced" => "-c:v libx264 -crf 23 -preset medium -profile:v main -level 4.0",
                        "Optimized" => "-c:v libx264 -crf 28 -preset fast -profile:v main -level 3.1",
                        "Tiny" => "-c:v libx264 -crf 32 -preset veryfast -profile:v baseline -level 3.0",
                        _ => "-c:v libx264 -crf 23 -preset medium -profile:v main -level 4.0"
                    };
                    codecAudio = KeepAudio ? "-acodec aac -b:a 128k" : "-an";
                    additionalArgs = "-movflags +faststart";
                    break;

                case "WebM (VP9/Opus)":
                    codecVideo = SelectedQuality switch
                    {
                        "Ultra" => "-c:v libvpx-vp9 -crf 10 -b:v 0 -cpu-used 0 -row-mt 1 -tile-columns 2",
                        "High" => "-c:v libvpx-vp9 -crf 15 -b:v 0 -cpu-used 1 -row-mt 1 -tile-columns 1",
                        "Balanced" => "-c:v libvpx-vp9 -crf 25 -b:v 0 -cpu-used 2 -row-mt 1",
                        "Optimized" => "-c:v libvpx-vp9 -crf 32 -b:v 0 -cpu-used 4 -row-mt 1",
                        "Tiny" => "-c:v libvpx-vp9 -crf 40 -b:v 0 -cpu-used 5 -deadline realtime",
                        _ => "-c:v libvpx-vp9 -crf 25 -b:v 0 -cpu-used 2 -row-mt 1"
                    };
                    codecAudio = KeepAudio ? "-acodec libopus -b:a 96k" : "-an";
                    additionalArgs = "";
                    break;

                default: // OGV
                    string baseTheoraArgs = SelectedQuality switch
                    {
                        "Ultra" => "-c:v libtheora -q:v 8 -qmin 6 -qmax 10 -threads 0",
                        "High" => "-c:v libtheora -q:v 7 -qmin 4 -qmax 9 -threads 0",
                        "Balanced" => "-c:v libtheora -q:v 6 -qmin 3 -qmax 8 -threads 0",
                        "Optimized" => "-c:v libtheora -q:v 5 -qmin 2 -qmax 7 -threads 0",
                        "Tiny" => "-c:v libtheora -q:v 3 -qmin 1 -qmax 5 -threads 0",
                        _ => "-c:v libtheora -q:v 6 -qmin 3 -qmax 8 -threads 0"
                    };

                    codecVideo = baseTheoraArgs;
                    codecAudio = KeepAudio ? "-c:a libvorbis -q:a 3 -ar 44100 -ac 2" : "-an";

                    additionalArgs = IsOgvModeEnabled ? GetOgvModeArguments() : "-pix_fmt yuv420p -g 30 -keyint_min 30 -threads 0";
                    break;
            }

            return (codecVideo, codecAudio, additionalArgs);
        }

        private string GetOgvModeArguments()
        {
            return SelectedOgvMode switch
            {
                "Constant FPS (CFR)" => "-pix_fmt yuv420p -g 15 -keyint_min 15 -vsync cfr",
                "Optimized for weak hardware" => "-pix_fmt yuv420p -g 60 -keyint_min 30 -bf 0 -threads 4 -slices 4",
                "Ideal Loop" => "-pix_fmt yuv420p -g 1 -keyint_min 1 -avoid_negative_ts make_zero -fflags +genpts",
                "Streaming Optimized" => "-pix_fmt yuv420p -g 15 -keyint_min 5 -bufsize 2000k -maxrate 1500k",
                "Mobile Optimized" => "-pix_fmt yuv420p -g 60 -keyint_min 30 -bf 0 -maxrate 800k -bufsize 1600k",
                _ => "-pix_fmt yuv420p -g 30 -keyint_min 30"
            };
        }

        private string BuildFilterChain()
        {
            string scaleFilter = "";
            if (!string.IsNullOrEmpty(SelectedResolution) && SelectedResolution != "Keep original")
            {
                var parts = SelectedResolution.Split('x');
                if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                {
                    scaleFilter = $"scale={w}:{h}:force_original_aspect_ratio=decrease";
                }
            }

            string fpsFilter = "";
            if (!string.IsNullOrWhiteSpace(Fps))
            {
                if (double.TryParse(Fps, out double fpsValue) && fpsValue > 0 && fpsValue <= 120)
                {
                    fpsFilter = $"fps={fpsValue}";
                }
            }

            if (!string.IsNullOrEmpty(scaleFilter) && !string.IsNullOrEmpty(fpsFilter))
                return $"{scaleFilter},{fpsFilter}";
            else if (!string.IsNullOrEmpty(scaleFilter))
                return scaleFilter;
            else if (!string.IsNullOrEmpty(fpsFilter))
                return fpsFilter;

            return "";
        }
    }
}