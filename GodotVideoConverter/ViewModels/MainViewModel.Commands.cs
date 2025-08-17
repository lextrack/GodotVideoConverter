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
    }
}