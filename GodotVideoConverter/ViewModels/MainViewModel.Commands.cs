using CommunityToolkit.Mvvm.Input;
using Microsoft.Win32;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
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
                        StatusMessage = "Invalid video file or ffmpeg and its resources are not found in the root folder";
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
        public void DeleteSelectedFile()
        {
            if (SelectedFileIndex >= 0 && SelectedFileIndex < InputFiles.Count)
            {
                int indexToRemove = SelectedFileIndex;
                string removedFile = InputFiles[indexToRemove];

                InputFiles.RemoveAt(indexToRemove);

                if (indexToRemove < VideoDetails.Count)
                {
                    VideoDetails.RemoveAt(indexToRemove);
                }

                if (InputFiles.Count == 0)
                {
                    SelectedFileIndex = -1;
                    VideoInfo = "";
                    Recommendations = "";
                    StatusMessage = "List cleared. Drag files here to convert";
                }
                else
                {
                    if (indexToRemove >= InputFiles.Count)
                    {
                        SelectedFileIndex = InputFiles.Count - 1;
                    }

                    StatusMessage = $"File removed: {Path.GetFileName(removedFile)}";

                    _ = UpdateVideoInfoAsync();
                }
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
        private async Task GenerateAtlasAsync()
        {
            if (InputFiles.Count == 0)
            {
                StatusMessage = "No files selected for atlas generation.";
                return;
            }

            IsGeneratingAtlas = true;
            Progress = 0;

            try
            {
                Directory.CreateDirectory(OutputFolder);

                StatusMessage = "Starting atlas generation...";

                int totalFiles = InputFiles.Count;
                int completedFiles = 0;

                foreach (var file in InputFiles)
                {
                    try
                    {
                        string fileName = Path.GetFileNameWithoutExtension(file);
                        StatusMessage = $"Generating atlas for {fileName}... ({completedFiles + 1}/{totalFiles})";

                        var fileProgressHandler = new Progress<int>(fileProgress =>
                        {
                            int totalProgress = (int)((completedFiles * 100.0 + fileProgress) / totalFiles);
                            Progress = Math.Min(totalProgress, 99);
                        });

                        await ConvertToSpriteAtlasAsync(file, OutputFolder, fileName, fileProgressHandler);

                        completedFiles++;
                        StatusMessage = $"Atlas created: {fileName}_atlas.png ({completedFiles}/{totalFiles})";
                    }
                    catch (InvalidOperationException ex)
                    {
                        StatusMessage = $"Error with {Path.GetFileNameWithoutExtension(file)}: {ex.Message}";

                        await Task.Delay(2000);

                        if (InputFiles.Count > 1)
                        {
                            StatusMessage += " - Continuing with next file...";
                            await Task.Delay(1000);
                            completedFiles++;
                            continue;
                        }
                        else
                        {
                            return;
                        }
                    }
                    catch (TimeoutException)
                    {
                        StatusMessage = $"Timeout processing {Path.GetFileNameWithoutExtension(file)}: Video took too long to process";

                        await Task.Delay(2000);

                        if (InputFiles.Count > 1)
                        {
                            StatusMessage += " - Continuing with next file...";
                            await Task.Delay(1000);
                            completedFiles++;
                            continue;
                        }
                        else
                        {
                            return;
                        }
                    }
                    catch (OutOfMemoryException)
                    {
                        StatusMessage = $"Insufficient memory for {Path.GetFileNameWithoutExtension(file)}: Reduce video resolution or duration";

                        await Task.Delay(2000);

                        if (InputFiles.Count > 1)
                        {
                            StatusMessage += " - Continuing with next file...";
                            await Task.Delay(1000);
                            completedFiles++;
                            continue;
                        }
                        else
                        {
                            return;
                        }
                    }
                    catch (Exception ex)
                    {
                        StatusMessage = $"Unexpected error with {Path.GetFileNameWithoutExtension(file)}: {ex.Message}";

                        System.Diagnostics.Debug.WriteLine($"Error generating atlas for {file}: {ex}");

                        await Task.Delay(2000);

                        if (InputFiles.Count > 1)
                        {
                            StatusMessage += " - Continuing with next file...";
                            await Task.Delay(1000);
                            completedFiles++;
                            continue;
                        }
                        else
                        {
                            return;
                        }
                    }
                }

                Progress = 100;
                if (completedFiles == totalFiles)
                {
                    StatusMessage = completedFiles == 1
                        ? "Atlas generated successfully!"
                        : $"All atlases generated! ({completedFiles}/{totalFiles} files)";
                }
                else
                {
                    StatusMessage = $"Generation completed: {completedFiles}/{totalFiles} files processed successfully";
                }
            }
            catch (UnauthorizedAccessException)
            {
                StatusMessage = "Permission error: Cannot write to destination folder. Check permissions or change folder.";
                Progress = 0;
            }
            catch (DirectoryNotFoundException)
            {
                StatusMessage = "Error: Destination folder does not exist or is invalid.";
                Progress = 0;
            }
            catch (Exception ex)
            {
                StatusMessage = $"General error: {ex.Message}";
                Progress = 0;

                System.Diagnostics.Debug.WriteLine($"General error in GenerateAtlasAsync: {ex}");
            }
            finally
            {
                IsGeneratingAtlas = false;
            }
        }
    }
}