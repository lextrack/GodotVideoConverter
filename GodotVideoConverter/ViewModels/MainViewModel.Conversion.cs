using CommunityToolkit.Mvvm.Input;
using System;
using System.IO;
using System.Threading.Tasks;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
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
                "Controlled Bitrate" => "-pix_fmt yuv420p -g 15 -keyint_min 5 -bufsize 2000k -maxrate 1500k",
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

        private string GetFileExtension()
        {
            return SelectedFormat switch
            {
                "MP4 (H.264/AAC)" => ".mp4",
                "WebM (VP9/Opus)" => ".webm",
                _ => ".ogv"
            };
        }

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

        private class ConversionParameters
        {
            public string OutputFile { get; set; } = "";
            public string Arguments { get; set; } = "";
        }
    }
}