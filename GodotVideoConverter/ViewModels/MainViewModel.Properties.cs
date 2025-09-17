using CommunityToolkit.Mvvm.ComponentModel;

namespace GodotVideoConverter.ViewModels
{
    public partial class MainViewModel
    {
        [ObservableProperty] private bool isConverting = false;
        [ObservableProperty] private string? selectedFormat;
        [ObservableProperty] private string? selectedResolution;
        [ObservableProperty] private string? selectedQuality;
        [ObservableProperty] private string? selectedOgvMode;
        [ObservableProperty] private bool keepAudio;
        [ObservableProperty] private string? fps;
        [ObservableProperty] private int progress;
        [ObservableProperty] private string statusMessage = "Drag the files to the box to convert them";
        [ObservableProperty] private string? outputFolder;
        [ObservableProperty] private bool isOgvModeEnabled;
        [ObservableProperty] private string videoInfo = "";
        [ObservableProperty] private string recommendations = "";
        [ObservableProperty] private int selectedFileIndex = -1;
        [ObservableProperty] private int atlasFps = 5;
        [ObservableProperty] private string? selectedAtlasMode = "Grid";
        [ObservableProperty] private string? selectedAtlasResolution = "Medium";
        [ObservableProperty] private bool keepOriginalAtlasResolution = true;
        [ObservableProperty] private bool isGeneratingAtlas = false;
        [ObservableProperty] private bool isLoadingFiles = false;
    }
}