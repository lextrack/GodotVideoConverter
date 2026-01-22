using CommunityToolkit.Mvvm.Input;
using System;
using System.IO;
using System.Threading.Tasks;
using GodotVideoConverter.Services;
using GodotVideoConverter.Models;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
        private async Task ConvertToSpriteAtlasAsync(string inputFile, string outputFolder, string fileName, IProgress<int> progressHandler)
        {
            await Task.Run(async () =>
            {
                var videoInfo = await _service.GetVideoInfoAsync(inputFile);
                int frameCount = (int)(videoInfo.Duration * AtlasFps);
                int resolutionWidth = videoInfo.Width;
                int resolutionHeight = videoInfo.Height;

                if (!string.IsNullOrEmpty(SelectedAtlasResolution) && SelectedAtlasResolution != "Keep Original")
                {
                    string resolutionValue = GetAtlasResolutionValue(SelectedAtlasResolution);
                    var parts = resolutionValue.Split('x');
                    if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                    {
                        resolutionWidth = w;
                        resolutionHeight = h;
                    }
                }

                int columns, rows;
                if (SelectedAtlasMode == "Horizontal")
                {
                    columns = frameCount;
                    rows = 1;
                }
                else if (SelectedAtlasMode == "Vertical")
                {
                    columns = 1;
                    rows = frameCount;
                }
                else // Grid
                {
                    columns = (int)Math.Ceiling(Math.Sqrt(frameCount));
                    rows = (int)Math.Ceiling((double)frameCount / columns);
                }

                long estimatedSizeBytes = (long)columns * rows * resolutionWidth * resolutionHeight * 4;
                const long maxSizeBytes = 200 * 1024 * 1024;

                if (estimatedSizeBytes > maxSizeBytes)
                {
                    StatusMessage = $"Warning: The atlas for {fileName} may exceed 200 MB ({estimatedSizeBytes / (1024 * 1024):F1} MB). This could take significant time or memory. Continuing...";
                    await Task.Delay(2000);
                }

                string outFile = Path.Combine(outputFolder, $"{fileName}_atlas.png");
                int counter = 1;
                while (File.Exists(outFile))
                {
                    outFile = Path.Combine(outputFolder, $"{fileName}_atlas_{counter}.png");
                    counter++;
                }

                string scaleFilter = "";
                if (!string.IsNullOrEmpty(SelectedAtlasResolution) && SelectedAtlasResolution != "Keep Original")
                {
                    string resolutionValue = GetAtlasResolutionValue(SelectedAtlasResolution);
                    var parts = resolutionValue.Split('x');
                    if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                    {
                        scaleFilter = $"scale={w}:{h}:force_original_aspect_ratio=decrease";
                    }
                }

                if (AtlasFps <= 0 || AtlasFps > 30)
                {
                    throw new InvalidOperationException($"Invalid atlas FPS: {AtlasFps}. Must be between 1 and 30.");
                }

                string atlasMode = SelectedAtlasMode ?? "Grid";

                var ffmpegProgress = new Progress<int>(p =>
                {
                    progressHandler.Report((int)(p * 0.8));
                });

                var atlasProgress = new Progress<int>(p =>
                {
                    progressHandler.Report(80 + (int)(p * 0.2));
                });

                await _service.ConvertToSpriteAtlasAsync(inputFile, outFile, AtlasFps, scaleFilter, atlasMode, ffmpegProgress);

                StatusMessage = $"Atlas created: {Path.GetFileName(outFile)}";
            });
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
            else
            {
                VideoInfo = $"Invalid video file: {fileName}";
                Recommendations = "No recommendations available for invalid video.";
            }
        }

        private bool ValidateConversionParameters()
        {
            if (string.IsNullOrWhiteSpace(OutputFolder))
            {
                StatusMessage = "Please select an output folder";
                return false;
            }

            if (string.IsNullOrEmpty(SelectedFormat))
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
                string filterArg = BuildFilterArgument();
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

                case "GIF (Animated)":
                    // GIF doesn't have a video codec parameter, filter is handled separately
                    codecVideo = "";
                    codecAudio = "-an"; // GIF doesn't support audio
                    additionalArgs = "-loop 0"; // 0 = infinite loop
                    break;

                default: // OGV
                    // Check if using CBR mode (Controlled Bitrate or Mobile Optimized)
                    bool useCBR = IsOgvModeEnabled && (SelectedOgvMode == "Controlled Bitrate" || SelectedOgvMode == "Mobile Optimized");

                    if (useCBR)
                    {
                        // For CBR modes, don't use -q:v (quality), bitrate is set in GetOgvModeArguments()
                        codecVideo = "-c:v libtheora -threads 0";
                    }
                    else
                    {
                        // For VBR modes, use quality settings
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
                    }

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
                "Constant FPS (CFR)" => "-pix_fmt yuv420p -g 15 -keyint_min 15 -fps_mode cfr",
                "Optimized for weak hardware" => "-pix_fmt yuv420p -g 60 -keyint_min 30 -threads 4",
                "Ideal Loop" => "-pix_fmt yuv420p -g 1 -keyint_min 1 -avoid_negative_ts make_zero -fflags +genpts",
                "Controlled Bitrate" => "-pix_fmt yuv420p -g 15 -keyint_min 5 -b:v 1200k -maxrate 1500k -bufsize 2000k",
                "Mobile Optimized" => "-pix_fmt yuv420p -g 60 -keyint_min 30 -b:v 600k -maxrate 800k -bufsize 1600k",
                _ => "-pix_fmt yuv420p -g 30 -keyint_min 30"
            };
        }

        private string BuildFilterArgument()
        {
            if (SelectedFormat == "GIF (Animated)")
            {
                return BuildGifFilter();
            }
            else
            {
                string filterChain = BuildFilterChain();
                return !string.IsNullOrEmpty(filterChain) ? $"-vf \"{filterChain}\"" : "";
            }
        }

        private string BuildGifFilter()
        {
            // Get user-defined scale and fps settings
            string userScale = "";
            if (!string.IsNullOrEmpty(SelectedResolution) && SelectedResolution != "Keep original")
            {
                var parts = SelectedResolution.Split('x');
                if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                {
                    userScale = $"scale={w}:{h}:force_original_aspect_ratio=decrease,";
                }
            }

            double userFps = 20; // default
            if (!string.IsNullOrWhiteSpace(Fps))
            {
                if (double.TryParse(Fps, out double fpsValue) && fpsValue > 0 && fpsValue <= 120)
                {
                    userFps = fpsValue;
                }
            }

            // Build GIF palette filter based on quality preset
            string paletteSettings = SelectedQuality switch
            {
                "Ultra" => "max_colors=256:stats_mode=diff",
                "High" => "max_colors=256:stats_mode=diff",
                "Balanced" => "max_colors=128:stats_mode=diff",
                "Optimized" => "max_colors=64:stats_mode=diff",
                "Tiny" => "max_colors=32:stats_mode=diff",
                _ => "max_colors=128:stats_mode=diff"
            };

            string ditherSettings = SelectedQuality switch
            {
                "Ultra" => "dither=bayer:bayer_scale=5",
                "High" => "dither=bayer:bayer_scale=4",
                "Balanced" => "dither=bayer:bayer_scale=3",
                "Optimized" => "dither=sierra2_4a",
                "Tiny" => "dither=sierra2_4a",
                _ => "dither=bayer:bayer_scale=3"
            };

            string gifFilter = $"fps={userFps},{userScale}scale=trunc(iw/2)*2:trunc(ih/2)*2:flags=lanczos,split[s0][s1];[s0]palettegen={paletteSettings}[p];[s1][p]paletteuse={ditherSettings}";

            return $"-vf \"{gifFilter}\"";
        }

        private string BuildFilterChain()
        {
            string scaleFilter = "";
            if (!string.IsNullOrEmpty(SelectedResolution) && SelectedResolution != "Keep original")
            {
                var parts = SelectedResolution.Split('x');
                if (parts.Length == 2 && int.TryParse(parts[0], out int w) && int.TryParse(parts[1], out int h))
                {
                    if (SelectedFormat?.StartsWith("MP4", StringComparison.OrdinalIgnoreCase) == true)
                    {
                        scaleFilter = $"scale={w}:{h}:force_original_aspect_ratio=decrease,scale='trunc(iw/2)*2':'trunc(ih/2)*2'";
                    }
                    else
                    {
                        scaleFilter = $"scale={w}:{h}:force_original_aspect_ratio=decrease";
                    }
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

            string combinedFilter = "";
            if (!string.IsNullOrEmpty(scaleFilter) && !string.IsNullOrEmpty(fpsFilter))
                combinedFilter = $"{scaleFilter},{fpsFilter}";
            else if (!string.IsNullOrEmpty(scaleFilter))
                combinedFilter = scaleFilter;
            else if (!string.IsNullOrEmpty(fpsFilter))
                combinedFilter = fpsFilter;

            return combinedFilter;
        }

        private string GetFileExtension()
        {
            return SelectedFormat switch
            {
                "MP4 (H.264/AAC)" => ".mp4",
                "WebM (VP9/Opus)" => ".webm",
                "GIF (Animated)" => ".gif",
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