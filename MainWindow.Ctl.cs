using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;

namespace HekatanOpenSees
{
    // Canal de control para probar la ventana desde una terminal (igual que el --ctl de Hekatan Lab):
    //   HekatanOpenSees.exe --ctl <carpeta>      escribe cmd-0001.json, lee resp-0001.json
    //   HekatanOpenSees.exe modelo.tcl --wshot v.png   corre, captura la VENTANA completa y sale
    // Ops: run · edit {text} (con AutoRun) · settext {text} · open {path} · theme {dark|claro} · capture {path} (ventana) · shot {path} (reporte completo)
    //      · menu {name,sub} · insertar {tag} · corroborar · gettext · status · quit
    public partial class MainWindow
    {
        [DllImport("user32.dll")] private static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
        [DllImport("user32.dll")] private static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
        [StructLayout(LayoutKind.Sequential)] private struct RECT { public int L, T, R, B; }

        private System.Windows.Controls.Menu FindVisualMenu()
        {
            System.Windows.Controls.Menu found = null;
            void Walk(DependencyObject d) { if (found != null) return; if (d is System.Windows.Controls.Menu m) { found = m; return; }
                for (int i = 0; i < System.Windows.Media.VisualTreeHelper.GetChildrenCount(d); i++) Walk(System.Windows.Media.VisualTreeHelper.GetChild(d, i)); }
            Walk(this); return found;
        }
        private string _ctlDir;
        private int _ctlSeq = 1;

        private void StartCtl(string dir)
        {
            _ctlDir = dir;
            Directory.CreateDirectory(dir);
            var t = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(250) };
            t.Tick += async (s, e) =>
            {
                var cmd = Path.Combine(_ctlDir, $"cmd-{_ctlSeq:D4}.json");
                if (!File.Exists(cmd)) return;
                t.Stop();
                string resp;
                try { resp = await DoCtl(File.ReadAllText(cmd)); }
                catch (Exception ex) { resp = JsonSerializer.Serialize(new { ok = false, error = ex.Message }); }
                File.WriteAllText(Path.Combine(_ctlDir, $"resp-{_ctlSeq:D4}.json"), resp);
                _ctlSeq++;
                t.Start();
            };
            t.Start();
        }

        private async Task<string> DoCtl(string json)
        {
            using var doc = JsonDocument.Parse(json);
            var r = doc.RootElement;
            string op = r.GetProperty("op").GetString();
            string Arg(string k) => r.TryGetProperty(k, out var v) ? v.GetString() : null;
            switch (op)
            {
                case "run": { var h = await RunCore(); await Task.Delay(2500); ApplyReportTheme(); return Ok(new { html = h, status = StatusText.Text }); }
                case "settext": _noAutoRun = true; try { Editor.Text = Arg("text") ?? ""; } finally { _noAutoRun = false; } return Ok(new { });
                case "edit": Editor.Text = Arg("text") ?? ""; return Ok(new { });   // cambia el texto CON AutoRun (como escribir); "settext" lo suprime
                case "linea": { int n = int.Parse(Arg("n")); Editor.ScrollTo(Math.Max(1, n), 1); Editor.TextArea.Caret.Line = Math.Max(1, n); await Task.Delay(300); return Ok(new { }); }   // lleva el editor a la linea n
                case "menu": {   // abre un menu superior por su nombre (Archivo, Editar, Ejemplos, Modelo...) y, con sub=Texto, su submenu; name="" los cierra
                    string name = (Arg("name") ?? "Ejemplos").Trim(), sub = Arg("sub");
                    Topmost = true; Activate();
                    var bar = (System.Windows.Controls.Menu)LogicalTreeHelper.FindLogicalNode(this, "MainMenu") ?? FindVisualMenu();
                    foreach (var it in bar.Items) if (it is System.Windows.Controls.MenuItem top) {
                        string h = (top.Header as string ?? "").Replace("_", "");
                        top.IsSubmenuOpen = name.Length > 0 && h.Equals(name, StringComparison.OrdinalIgnoreCase);
                        if (top.IsSubmenuOpen && !string.IsNullOrEmpty(sub))
                            foreach (var c in top.Items) if (c is System.Windows.Controls.MenuItem cm && (cm.Header as string ?? "").StartsWith(sub)) cm.IsSubmenuOpen = true;
                    }
                    await Task.Delay(600); if (name.Length == 0) Topmost = false; return Ok(new { });
                }
                case "insertar": { if (Snippets.TryGetValue(Arg("tag"), out var snip)) InsertAtCursor(snip); await Task.Delay(300); return Ok(new { }); }   // como elegir esa opcion del menu
                case "corroborar": { _ = Dispatcher.BeginInvoke(new Action(() => Corroborar_Click(null, null))); await Task.Delay(500); return Ok(new { }); }
                case "ejemplo": {   // como elegir ese ejemplo en el menu Ejemplos (por parte del nombre)
                    foreach (var it in ExamplesMenu.Items) { if (it is System.Windows.Controls.MenuItem g) { if (g.Header is string gh && gh.StartsWith(Arg("name") ?? "~~")) { Example_Click(g, null); return Ok(new { }); }
                        foreach (var c in g.Items) if (c is System.Windows.Controls.MenuItem cm && cm.Header is string ch && ch.StartsWith(Arg("name") ?? "~~")) { Example_Click(cm, null); return Ok(new { }); } } }
                    return Ok(new { error = "ejemplo no encontrado" }); }
                case "abrir": { _file = Arg("path"); Editor.Text = File.ReadAllText(Arg("path")); Title = "Hekatan OpenSees — " + Path.GetFileName(Arg("path")); return Ok(new { }); }   // como Archivo > Abrir (sin dialogo)
                case "gettext": return Ok(new { text = Editor.Text });
                case "open": _noAutoRun = true; try { Editor.Text = File.ReadAllText(Arg("path")); } finally { _noAutoRun = false; } _file = Arg("path"); return Ok(new { });
                case "theme": SetTheme(!string.Equals(Arg("mode"), "claro", StringComparison.OrdinalIgnoreCase)); await Task.Delay(400); return Ok(new { dark = _dark });
                case "solo": await ToggleSolo(Arg("on") != "0"); await Task.Delay(600); return Ok(new { solo = _solo });
                case "capture": CaptureWindowPng(Arg("path")); return Ok(new { path = Arg("path") });
                case "shot": await CaptureWebViewPng(Arg("path")); return Ok(new { path = Arg("path") });
                case "js": { var res = await Web.CoreWebView2.ExecuteScriptAsync(Arg("code")); await Task.Delay(400); return Ok(new { result = res }); }
                case "status": return Ok(new { status = StatusText.Text, dark = _dark, runs = _runCount, auto = AutoRun.IsChecked == true });
                case "quit": Dispatcher.BeginInvoke(new Action(() => Application.Current.Shutdown())); return Ok(new { });
                default: return JsonSerializer.Serialize(new { ok = false, error = "op desconocida: " + op });
            }
        }

        private static string Ok(object extra)
        {
            var d = new System.Collections.Generic.Dictionary<string, object> { ["ok"] = true };
            foreach (var p in extra.GetType().GetProperties()) d[p.Name] = p.GetValue(extra);
            return JsonSerializer.Serialize(d);
        }

        // «Solo animación»: se esconde el editor y la grafica ocupa la ventana; Esc o el mismo boton la devuelven
        private bool _solo;
        private async void Solo_Click(object sender, RoutedEventArgs e) => await ToggleSolo(!_solo);

        private async System.Threading.Tasks.Task ToggleSolo(bool on)
        {
            _solo = on;
            ColEditor.Width = on ? new GridLength(0) : new GridLength(1.05, GridUnitType.Star);
            ColSplit.Width = on ? new GridLength(0) : new GridLength(6);
            try
            {
                await Web.EnsureCoreWebView2Async();
                await Web.CoreWebView2.ExecuteScriptAsync("(window.HKGRIETA&&HKGRIETA.solo(" + (on ? "true" : "false") + "),window.HKMODOS&&HKMODOS.solo(" + (on ? "true" : "false") + "))");
            }
            catch { }
            StatusText.Text = on ? "Solo animación (Esc para volver)" : "Listo";
        }

        // Captura la ventana ENTERA (menu, editor, WebView2) con PrintWindow: no depende de lo que haya encima en pantalla.
        private void CaptureWindowPng(string png)
        {
            var hwnd = new WindowInteropHelper(this).Handle;
            GetWindowRect(hwnd, out var rc);
            int w = rc.R - rc.L, h = rc.B - rc.T;
            using var bmp = new System.Drawing.Bitmap(w, h);
            using (var g = System.Drawing.Graphics.FromImage(bmp))
            {
                var hdc = g.GetHdc();
                PrintWindow(hwnd, hdc, 2);          // PW_RENDERFULLCONTENT: incluye el contenido del WebView2
                g.ReleaseHdc(hdc);
            }
            bmp.Save(png, System.Drawing.Imaging.ImageFormat.Png);
        }

        // --wshot: corre el modelo, espera el dibujo, guarda la ventana completa y cierra
        private async Task WindowShotAndExit(string png)
        {
            await Task.Delay(3500);
            ApplyReportTheme();
            await Task.Delay(500);
            CaptureWindowPng(png);
            Application.Current.Shutdown();
        }
    }
}
