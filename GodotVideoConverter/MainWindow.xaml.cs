using GodotVideoConverter.ViewModels;
using GodotVideoConverter.Views;
using System.Diagnostics;
using System.Windows;
using System.Windows.Input;

namespace GodotVideoConverter
{
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();
        }

        private void Window_DragOver(object sender, DragEventArgs e)
        {
            e.Effects = e.Data.GetDataPresent(DataFormats.FileDrop) ? DragDropEffects.Copy : DragDropEffects.None;
            e.Handled = true;
        }

        private async void Window_Drop(object sender, DragEventArgs e)
        {
            if (e.Data.GetDataPresent(DataFormats.FileDrop))
            {
                var files = (string[])e.Data.GetData(DataFormats.FileDrop);
                if (DataContext is MainViewModel vm)
                {
                    if (vm.IsLoadingFiles)
                    {
                        vm.StatusMessage = "Please wait until current files are validated.";
                        return;
                    }
                    await vm.AddFilesAsync(files);
                }
            }
        }

        private void FileListBox_KeyDown(object sender, KeyEventArgs e)
        {
            if (e.Key == Key.Delete && DataContext is MainViewModel viewModel)
            {
                viewModel.DeleteSelectedFileCommand.Execute(null);
                e.Handled = true;
            }
        }

        private void NumbersOnly_PreviewTextInput(object sender, TextCompositionEventArgs e)
        {
            e.Handled = !IsTextAllowed(e.Text);
        }

        private static bool IsTextAllowed(string text)
        {
            return text.All(char.IsDigit);
        }

        private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            if (DataContext is MainViewModel vm && (vm.IsConverting || vm.IsGeneratingAtlas))
            {
                var result = MessageBox.Show(
                    "A video conversion or sprite atlas generation is in progress. Are you sure you want to exit?\nThis will cancel the current operation.",
                    "Operation in Progress",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Warning);

                if (result == MessageBoxResult.No)
                {
                    e.Cancel = true;
                    return;
                }

                if (vm.IsConverting || vm.IsGeneratingAtlas)
                {
                    vm.CancelConversionCommand.Execute(null);

                    System.Threading.Thread.Sleep(500);
                }

                KillFFmpegProcesses();
            }
        }

        private void KillFFmpegProcesses()
        {
            try
            {
                var ffmpegProcesses = Process.GetProcessesByName("ffmpeg");
                var ffprobeProcesses = Process.GetProcessesByName("ffprobe");

                foreach (var process in ffmpegProcesses)
                {
                    try
                    {
                        if (!process.HasExited)
                        {
                            process.Kill();
                            process.WaitForExit(2000);
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"Error killing ffmpeg process: {ex.Message}");
                    }
                    finally
                    {
                        process.Dispose();
                    }
                }

                foreach (var process in ffprobeProcesses)
                {
                    try
                    {
                        if (!process.HasExited)
                        {
                            process.Kill();
                            process.WaitForExit(2000);
                        }
                    }
                    catch (Exception ex)
                    {
                        Debug.WriteLine($"Error killing ffprobe process: {ex.Message}");
                    }
                    finally
                    {
                        process.Dispose();
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"Error during process cleanup: {ex.Message}");
            }
        }

        private void AboutButton_Click(object sender, RoutedEventArgs e)
        {
            var aboutWindow = new AboutWindow();
            aboutWindow.Owner = this;
            aboutWindow.ShowDialog();
        }
    }
}