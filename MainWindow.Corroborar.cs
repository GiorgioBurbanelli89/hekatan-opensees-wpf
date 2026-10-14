using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;

namespace HekatanOpenSees
{
    // Guardar como OpenSees Tcl ejecutable y corroborar con el OpenSees oficial (como "Guardar como LISP ejecutable" / juez de Hekatan LISP).
    public partial class MainWindow
    {
        private static string Cabecera() =>
            "# Hekatan OpenSees - guion ejecutable en OpenSees (Tcl). Las lineas # son comentarios para OpenSees;" + Environment.NewLine +
            "# Hekatan OpenSees las usa para el reporte (## titulo, #gfx ... #endgfx = graficas de Hekatan Lab)." + Environment.NewLine;

        private void SaveTclExec_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.SaveFileDialog { Filter = "OpenSees Tcl (*.tcl)|*.tcl", FileName = _file != null ? Path.GetFileName(_file) : "modelo.tcl" };
            if (dlg.ShowDialog() != true) return;
            string txt = Editor.Text;
            if (!txt.StartsWith("# Hekatan OpenSees")) txt = Cabecera() + txt;
            File.WriteAllText(dlg.FileName, txt, new UTF8Encoding(false));
            StatusText.Text = "Guardado como OpenSees Tcl ejecutable: " + Path.GetFileName(dlg.FileName);
        }

        private async void Corroborar_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                StatusText.Text = "Corroborando con el OpenSees oficial…";
                var tcl = Path.Combine(_tmp, "corroborar.tcl");
                File.WriteAllText(tcl, Editor.Text, new UTF8Encoding(false));
                var psi = new ProcessStartInfo("python", $"\"{Path.Combine(AppContext.BaseDirectory, "corroborar.py")}\" \"{tcl}\"")
                {
                    RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true,
                    StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8
                };
                psi.Environment["PYTHONIOENCODING"] = "utf-8";
                using var p = Process.Start(psi);
                var so = p.StandardOutput.ReadToEndAsync();
                var se = p.StandardError.ReadToEndAsync();
                await Task.Run(() => p.WaitForExit());
                string txt = (await so) + (await se);
                StatusText.Text = p.ExitCode == 0 ? "Corroborado con OpenSees oficial" : "Corroboración: ver detalle";
                var tb = new TextBox
                {
                    Text = txt, IsReadOnly = true, FontFamily = new System.Windows.Media.FontFamily("Cascadia Code, Consolas"), FontSize = 13,
                    Background = (System.Windows.Media.Brush)FindResource("ThemeEditorBg"), Foreground = (System.Windows.Media.Brush)FindResource("ThemeText"),
                    BorderThickness = new Thickness(0), Padding = new Thickness(10), VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
                    HorizontalScrollBarVisibility = ScrollBarVisibility.Auto
                };
                new Window { Title = "Corroborar con OpenSees oficial", Content = tb, Width = 860, Height = 420, Owner = this, Background = (System.Windows.Media.Brush)FindResource("ThemeWindowBg") }.Show();
            }
            catch (Exception ex) { StatusText.Text = "Error: " + ex.Message; }
        }
    }
}
