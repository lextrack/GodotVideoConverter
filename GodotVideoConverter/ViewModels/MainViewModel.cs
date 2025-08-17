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

        public ObservableCollection<string> Qualities { get; } = new()
        {
            "Ultra", "High", "Balanced", "Optimized", "Tiny"
        };

        public ObservableCollection<string> OgvModes { get; } = new()
        {
            "Standard", "Constant FPS (CFR)", "Optimized for weak hardware", "Ideal Loop", "Streaming Optimized", "Mobile Optimized"
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
                        StatusMessage = $"Invalid video file: {Path.GetFileName(file)}";
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

        [RelayCommand]
        public async Task ConvertAsync()
        {
            if (InputFiles.Count == 0)
            {
                StatusMessage = "No files selected.";
                return;
            }

            IsConverting = true;

            try
            {
                Directory.CreateDirectory(OutputFolder);

                foreach (var file in InputFiles)
                {
                    string fileName = Path.GetFileNameWithoutExtension(file);
                    string extension;
                    string codecVideo;
                    string codecAudio;
                    string additionalArgs = "";

                    switch (SelectedFormat)
                    {
                        case "MP4 (H.264/AAC)":
                            extension = ".mp4";
                            codecVideo = SelectedQuality switch
                            {
                                "Ultra" => "-vcodec libx264 -crf 15 -preset slower",
                                "High" => "-vcodec libx264 -crf 18 -preset slow",
                                "Balanced" => "-vcodec libx264 -crf 23 -preset medium",
                                "Optimized" => "-vcodec libx264 -crf 28 -preset fast",
                                "Tiny" => "-vcodec libx264 -crf 35 -preset veryfast",
                                _ => "-vcodec libx264 -crf 23 -preset medium"
                            };
                            codecAudio = KeepAudio ? "-acodec aac -b:a 128k" : "-an";
                            break;

                        case "WebM (VP9/Opus)":
                            extension = ".webm";
                            codecVideo = SelectedQuality switch
                            {
                                "Ultra" => "-vcodec libvpx-vp9 -crf 10 -b:v 0 -cpu-used 0",
                                "High" => "-vcodec libvpx-vp9 -crf 15 -b:v 0 -cpu-used 1",
                                "Balanced" => "-vcodec libvpx-vp9 -crf 25 -b:v 0 -cpu-used 2",
                                "Optimized" => "-vcodec libvpx-vp9 -crf 35 -b:v 0 -cpu-used 4",
                                "Tiny" => "-vcodec libvpx-vp9 -crf 45 -b:v 0 -cpu-used 8",
                                _ => "-vcodec libvpx-vp9 -crf 25 -b:v 0 -cpu-used 2"
                            };
                            codecAudio = KeepAudio ? "-acodec libopus -b:a 96k" : "-an";
                            break;

                        default:
                            extension = ".ogv";
                            string baseTheoraArgs = SelectedQuality switch
                            {
                                "Ultra" => "-c:v libtheora -q:v 8 -threads 0 -speed 0",
                                "High" => "-c:v libtheora -q:v 7 -threads 0 -speed 1",
                                "Balanced" => "-c:v libtheora -q:v 6 -threads 0 -speed 2",
                                "Optimized" => "-c:v libtheora -q:v 5 -threads 0 -speed 3",
                                "Tiny" => "-c:v libtheora -q:v 3 -threads 0 -speed 4",
                                _ => "-c:v libtheora -q:v 6 -threads 0 -speed 2"
                            };

                            codecVideo = baseTheoraArgs;
                            codecAudio = KeepAudio ? "-c:a libvorbis -q:a 3 -ar 44100 -ac 2" : "-an";

                            if (IsOgvModeEnabled)
                            {
                                additionalArgs = SelectedOgvMode switch
                                {
                                    "Constant FPS (CFR)" =>
                                        $"-pix_fmt yuv420p -g 15 -keyint_min 15 -r {Fps} -vsync cfr",

                                    "Optimized for weak hardware" =>
                                        "-pix_fmt yuv420p -g 60 -keyint_min 30 -bf 0 -threads 2",

                                    "Ideal Loop" =>
                                        "-pix_fmt yuv420p -g 1 -keyint_min 1 -avoid_negative_ts make_zero -fflags +genpts",

                                    "Streaming Optimized" =>
                                        "-pix_fmt yuv420p -g 15 -keyint_min 5",

                                    "Mobile Optimized" =>
                                        "-pix_fmt yuv420p -g 60 -keyint_min 30 -bf 0 -maxrate 800k -bufsize 1600k",

                                    _ =>
                                        "-pix_fmt yuv420p -g 30 -keyint_min 30"
                                };

                            }
                            else
                            {
                                additionalArgs = "-pix_fmt yuv420p -g 30 -keyint_min 30 -threads 0 -row-mt 1";
                            }
                            break;
                    }

                    string outFileBase = Path.Combine(OutputFolder, fileName + "_converted" + extension);
                    string outFile = outFileBase;
                    int counter = 1;
                    while (File.Exists(outFile))
                    {
                        outFile = Path.Combine(OutputFolder, $"{fileName}_converted_{counter}{extension}");
                        counter++;
                    }

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
                        if (double.TryParse(Fps, out double fpsValue) && fpsValue > 0)
                        {
                            fpsFilter = $"fps={Fps}";
                        }
                        else
                        {
                            fpsFilter = "fps=30";
                        }
                    }

                    string filterChain = "";
                    if (!string.IsNullOrEmpty(scaleFilter) && !string.IsNullOrEmpty(fpsFilter))
                        filterChain = $"{scaleFilter},{fpsFilter}";
                    else if (!string.IsNullOrEmpty(scaleFilter))
                        filterChain = scaleFilter;
                    else if (!string.IsNullOrEmpty(fpsFilter))
                        filterChain = fpsFilter;

                    string filterArg = !string.IsNullOrEmpty(filterChain) ? $"-vf \"{filterChain}\"" : "";

                    double duration = await _service.GetVideoDurationAsync(file);
                    if (duration <= 0)
                    {
                        StatusMessage = $"Could not read duration of {fileName}";
                        continue;
                    }

                    string args = $"-i \"{file}\" {filterArg} {codecVideo} {codecAudio} {additionalArgs} \"{outFile}\"";

                    var progressHandler = new Progress<int>(p => Progress = p);
                    StatusMessage = $"Converting {fileName}...";

                    try
                    {
                        await _service.ConvertAsync(file, outFile, args, duration, progressHandler);
                        StatusMessage = $"Converted: {Path.GetFileName(outFile)}";
                    }
                    catch (Exception ex)
                    {
                        StatusMessage = $"Error converting {fileName}: {ex.Message}";
                    }
                }

                StatusMessage = "All conversions completed!";
            }
            finally
            {
                IsConverting = false;
            }
        }
    }
}