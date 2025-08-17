using CommunityToolkit.Mvvm.ComponentModel;
using CommunityToolkit.Mvvm.Input;
using GodotVideoConverter.Models;
using GodotVideoConverter.Services;
using System;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Windows.Threading;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel : ObservableObject, IDisposable
    {
        private readonly VideoConversionService _service;
        private readonly VideoRecommendationService _recommendationService;
        public ObservableCollection<string> InputFiles { get; } = new();
        public ObservableCollection<VideoInfo> VideoDetails { get; } = new();

        public MainViewModel()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            _service = new VideoConversionService(baseDir);
            _recommendationService = new VideoRecommendationService();
            InitializeTimer();
            LoadSettings();
            UpdateOgvModeAvailability();
            _isInitialized = true;
        }

        private void InitializeTimer()
        {
            _saveTimer = new DispatcherTimer
            {
                Interval = TimeSpan.FromMilliseconds(500)
            };
            _saveTimer.Tick += (s, e) =>
            {
                _saveTimer.Stop();
                SaveSettings();
            };
        }

        public void Dispose()
        {
            _service.Dispose();
            _saveTimer?.Stop();
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
        public void OpenOutputFolder()
        {
            Directory.CreateDirectory(OutputFolder);

            try
            {
                Process.Start(new ProcessStartInfo()
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
    }
}