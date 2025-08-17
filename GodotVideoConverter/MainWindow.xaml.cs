using GodotVideoConverter.ViewModels;
using GodotVideoConverter.Views;
using System.Diagnostics;
using System.Windows;

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
                    await vm.AddFilesAsync(files);
                }
            }
        }

        private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            if (DataContext is MainViewModel vm && vm.IsConverting)
            {
                var result = MessageBox.Show(
                    "A video conversion is in progress. Are you sure you want to exit?\nThis will cancel the current conversion.",
                    "Conversion in Progress",
                    MessageBoxButton.YesNo,
                    MessageBoxImage.Warning);

                if (result == MessageBoxResult.No)
                {
                    e.Cancel = true;
                }
                else
                {
                    KillFFmpegProcesses();
                }
            }
        }

        private void KillFFmpegProcesses()
        {
            try
            {
                foreach (var process in Process.GetProcessesByName("ffmpeg"))
                {
                    try
                    {
                        process.Kill();
                        process.WaitForExit(2000);
                    }
                    catch
                    {

                    }
                }

                foreach (var process in Process.GetProcessesByName("ffprobe"))
                {
                    try
                    {
                        process.Kill();
                        process.WaitForExit(1000);
                    }
                    catch
                    {

                    }
                }
            }
            catch
            {

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