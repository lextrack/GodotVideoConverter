using System;
using System.IO;
using System.Windows.Threading;
using GodotVideoConverter.Properties;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
        private DispatcherTimer? _saveTimer;
        private bool _isInitialized = false;

        private void LoadSettings()
        {
            try
            {
                OutputFolder = Settings.Default.OutputFolder;
                SelectedFormat = Settings.Default.SelectedFormat;
                SelectedResolution = Settings.Default.SelectedResolution;
                SelectedQuality = Settings.Default.SelectedQuality;
                SelectedOgvMode = Settings.Default.SelectedOgvMode;
                KeepAudio = Settings.Default.KeepAudio;
                Fps = Settings.Default.Fps;

                AtlasFps = Settings.Default.AtlasFps;
                SelectedAtlasMode = Settings.Default.SelectedAtlasMode;
                SelectedAtlasResolution = Settings.Default.SelectedAtlasResolution;

                if (string.IsNullOrEmpty(OutputFolder))
                {
                    OutputFolder = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "output");
                }
                if (string.IsNullOrEmpty(SelectedFormat))
                {
                    SelectedFormat = "OGV (Default for Godot)";
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

                if (AtlasFps <= 0)
                {
                    AtlasFps = 5;
                }
                if (string.IsNullOrEmpty(SelectedAtlasMode))
                {
                    SelectedAtlasMode = "Grid";
                }
                if (string.IsNullOrEmpty(SelectedAtlasResolution))
                {
                    SelectedAtlasResolution = "Medium";
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
            SelectedFormat = "OGV (Default for Godot)";
            SelectedResolution = "Keep original";
            SelectedQuality = "Optimized";
            SelectedOgvMode = "Standard";
            Fps = "30";
            KeepAudio = false;

            AtlasFps = 5;
            SelectedAtlasMode = "Grid";
            SelectedAtlasResolution = "Medium";
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
                Settings.Default.OutputFolder = OutputFolder;
                Settings.Default.SelectedFormat = SelectedFormat ?? "";
                Settings.Default.SelectedResolution = SelectedResolution ?? "";
                Settings.Default.SelectedQuality = SelectedQuality ?? "";
                Settings.Default.SelectedOgvMode = SelectedOgvMode ?? "";
                Settings.Default.KeepAudio = KeepAudio;
                Settings.Default.Fps = Fps ?? "";

                Settings.Default.AtlasFps = AtlasFps;
                Settings.Default.SelectedAtlasMode = SelectedAtlasMode ?? "";
                Settings.Default.SelectedAtlasResolution = SelectedAtlasResolution ?? "";

                Settings.Default.Save();
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

        partial void OnAtlasFpsChanged(int value)
        {
            if (value > 30)
            {
                AtlasFps = 30;
                StatusMessage = "Maximum FPS is 30. Value has been set to 30.";
            }
            else if (value < 1)
            {
                AtlasFps = 1;
                StatusMessage = "Minimum FPS is 1. Value has been set to 1.";
            }
            else
            {
                StatusMessage = "";
            }

            SaveSettingsDelayed();
        }

        partial void OnSelectedAtlasModeChanged(string? value)
        {
            SaveSettingsDelayed();
        }

        partial void OnSelectedAtlasResolutionChanged(string? value)
        {
            SaveSettingsDelayed();
        }
    }
}