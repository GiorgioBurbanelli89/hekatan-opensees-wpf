using System.Linq;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;

namespace HekatanOpenSees
{
    public partial class MainWindow : Window
    {
        private string _file;
        private readonly string _tmp = Path.Combine(Path.GetTempPath(), "oscalc_session");
        private readonly DispatcherTimer _autoTimer;   // AutoRun con retardo (debounce), como Calcpad

        public MainWindow()
        {
            InitializeComponent();
            SetupEditor();
            Directory.CreateDirectory(_tmp);

            // Argumentos:  HekatanOpenSees.exe [modelo.tcl] [--shot salida.png]
            //   modelo.tcl   -> abre y corre ese ejemplo en la app
            //   --shot p.png -> ademas captura el WebView2 a PNG (render del propio motor Edge)
            string openTcl = null, shotPng = null, htmlDirect = null, wshotPng = null, ctlDir = null; bool hover = false;
            var argv = Environment.GetCommandLineArgs();
            for (int i = 1; i < argv.Length; i++)
            {
                if (argv[i] == "--shot" && i + 1 < argv.Length) shotPng = argv[++i];
                else if (argv[i] == "--html" && i + 1 < argv.Length) htmlDirect = argv[++i];
                else if (argv[i] == "--wshot" && i + 1 < argv.Length) wshotPng = argv[++i];
                else if (argv[i] == "--ctl" && i + 1 < argv.Length) ctlDir = argv[++i];
                else if (argv[i] == "--hover") hover = true;
                else if (argv[i].EndsWith(".tcl", StringComparison.OrdinalIgnoreCase) && File.Exists(argv[i])) openTcl = argv[i];
            }
            if (openTcl != null) { _file = openTcl; Title = "Hekatan OpenSees — " + Path.GetFileName(openTcl); }
            Editor.Text = openTcl != null ? File.ReadAllText(openTcl) : Sample;
            PopulateExamplesMenu();

            // AutoRun: tras dejar de escribir ~700 ms, recalcula (como el AutoRun de Calcpad)
            _autoTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(700) };
            _autoTimer.Tick += (s, e) => { _autoTimer.Stop(); Run(); };

            InputBindings.Add(new KeyBinding(new RelayCommand(_ => _ = ToggleSolo(!_solo)), Key.F11, ModifierKeys.None));
            InputBindings.Add(new KeyBinding(new RelayCommand(_ => { if (_solo) _ = ToggleSolo(false); }), Key.Escape, ModifierKeys.None));
            InputBindings.Add(new KeyBinding(new RelayCommand(_ => Run()), Key.F5, ModifierKeys.None));
            InputBindings.Add(new KeyBinding(new RelayCommand(_ => Save()), Key.S, ModifierKeys.Control));
            Loaded += async (s, e) =>
            {
                try { await Web.EnsureCoreWebView2Async(); Web.CoreWebView2.NavigationCompleted += (s2, e2) => ApplyReportTheme(); HookDibujo(); } catch { }
                SetTheme(!Environment.GetCommandLineArgs().Contains("--claro"));
                if (openTcl != null || shotPng != null || htmlDirect != null) await RunAndShot(shotPng, hover, htmlDirect);
                if (wshotPng != null) await WindowShotAndExit(wshotPng);
                // al abrir sin archivo ya hay un script de ejemplo: con AutoRun marcado se calcula solo (antes el reporte quedaba vacio hasta escribir algo)
                if (openTcl == null && shotPng == null && htmlDirect == null && wshotPng == null && ctlDir == null && AutoRun.IsChecked == true) Run();
                if (ctlDir != null) StartCtl(ctlDir);
            };
        }

        // ===================== TEMA (copiado de Hekatan Lab: Oscuro | Claro "oro") =====================
        private bool _dark = true;
        private bool _ranOnce;
        private static readonly (string key, string dark, string gold)[] _themeBrushes =
        {
            ("ThemeWindowBg",     "#141109", "#E9DFC6"),
            ("ThemePanelBg",      "#1C1810", "#F1E9D6"),
            ("ThemeEditorBg",     "#1A1712", "#F8F2E4"),
            ("ThemeText",         "#E8E2D4", "#2B2416"),
            ("ThemeTextMuted",    "#A89F8C", "#6B5E45"),
            ("ThemeAccentRed",    "#E5382B", "#C0392B"),
            ("ThemeAccentGold",   "#E6C463", "#A9820C"),
            ("ThemeButtonBg",     "#262016", "#EFE7D2"),
            ("ThemeButtonBorder", "#3A3226", "#CBBD98"),
            ("ThemeGutterBg",     "#211D16", "#E4DAC0"),
            ("ThemeHoverBg",      "#33E5382B", "#33C0392B"),
        };

        private void SetTheme(bool dark)
        {
            _dark = dark;
            var conv = new System.Windows.Media.BrushConverter();
            foreach (var (key, d, g) in _themeBrushes)
            {
                var b = (System.Windows.Media.SolidColorBrush)conv.ConvertFromString(dark ? d : g);
                b.Freeze();
                Resources[key] = b;
            }
            var menuText = (System.Windows.Media.SolidColorBrush)conv.ConvertFromString(dark ? "#E8E2D4" : "#2B2416");
            var menuBg = (System.Windows.Media.SolidColorBrush)conv.ConvertFromString(dark ? "#1C1810" : "#F1E9D6");
            Resources[SystemColors.MenuTextBrushKey] = menuText;
            Resources[SystemColors.MenuBrushKey] = menuBg;
            try { if (Web != null) Web.DefaultBackgroundColor = System.Drawing.ColorTranslator.FromHtml(dark ? "#141109" : "#E9DFC6"); } catch { }
            ApplyEditorTheme();
            ApplyReportTheme();
            if (_ranOnce) Run();            // el reporte (y sus gráficas) se vuelve a dibujar con los colores del tema
        }

        // Reporte: en oscuro se invierte la luminosidad de la pagina (fondo, texto y gráficas) conservando el matiz.
        private async void ApplyReportTheme()
        {
            try
            {
                if (Web?.CoreWebView2 == null) return;
                string css = _dark ? "html{background:#141109}" : "html{background:#fff}";
                string js = "(function(){var s=document.getElementById('hk-tema');if(!s){s=document.createElement('style');s.id='hk-tema';document.head.appendChild(s);}s.textContent="
                          + System.Text.Json.JsonSerializer.Serialize(css) + ";})()";
                await Web.CoreWebView2.ExecuteScriptAsync(js);
            }
            catch { }
        }

        private void ThemeDark_Click(object sender, RoutedEventArgs e) => SetTheme(true);
        private void ThemeLight_Click(object sender, RoutedEventArgs e) => SetTheme(false);

        // Corre el ejemplo y (si se pidio) captura el WebView2 a PNG de PAGINA COMPLETA
        // usando el protocolo DevTools (Page.captureScreenshot) del propio motor del WebView2.
        private async Task RunAndShot(string png, bool hover = false, string htmlDirect = null)
        {
            string html;
            if (htmlDirect != null)   // navega directo a un HTML (para comparar gráficas), sin correr OpenSees
            {
                await Web.EnsureCoreWebView2Async();
                Web.CoreWebView2.Navigate(new Uri(htmlDirect).AbsoluteUri);
                html = htmlDirect;
            }
            else html = await RunCore();
            if (png == null || html == null) return;
            try
            {
                await Task.Delay(2500);                // espera el dibujo diferido (setTimeout / surf 3D)
                if (hover)                             // simula el cursor sobre cada canvas para ver el datatip
                    await Web.CoreWebView2.ExecuteScriptAsync(
                        "(function(){var cs=document.querySelectorAll('canvas');for(var i=0;i<cs.length;i++){var r=cs[i].getBoundingClientRect();cs[i].dispatchEvent(new MouseEvent('mousemove',{clientX:r.left+r.width*0.5,clientY:r.top+r.height*0.45,bubbles:true}));}})()");
                await CaptureWebViewPng(png);
                StatusText.Text = "PNG del WebView2: " + png;
            }
            catch (Exception ex) { StatusText.Text = "Error captura: " + ex.Message; }
        }

        // Captura el WebView2 a PNG de PÁGINA COMPLETA (gráficas + resultados + ecuaciones) con DevTools.
        private async Task CaptureWebViewPng(string png)
        {
            await Web.EnsureCoreWebView2Async();
            var ci = System.Globalization.CultureInfo.InvariantCulture;
            var wStr = await Web.CoreWebView2.ExecuteScriptAsync("Math.max(document.body.scrollWidth,document.documentElement.scrollWidth)");
            var hStr = await Web.CoreWebView2.ExecuteScriptAsync("Math.max(document.body.scrollHeight,document.documentElement.scrollHeight)");
            int w = (int)double.Parse(wStr, ci), h = (int)double.Parse(hStr, ci);
            var prm = "{\"format\":\"png\",\"captureBeyondViewport\":true,\"clip\":{\"x\":0,\"y\":0,\"width\":" + w + ",\"height\":" + h + ",\"scale\":1}}";
            var res = await Web.CoreWebView2.CallDevToolsProtocolMethodAsync("Page.captureScreenshot", prm);
            using var doc = System.Text.Json.JsonDocument.Parse(res);
            File.WriteAllBytes(png, Convert.FromBase64String(doc.RootElement.GetProperty("data").GetString()));
        }

        // Menú / botón "Exportar PNG": guarda el reporte completo (gráficas, resultados, ecuaciones) como imagen.
        private async void ExportPng_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                var dlg = new Microsoft.Win32.SaveFileDialog { Filter = "Imagen PNG (*.png)|*.png", FileName = "reporte.png" };
                if (dlg.ShowDialog() == true)
                {
                    await CaptureWebViewPng(dlg.FileName);
                    StatusText.Text = "PNG exportado: " + Path.GetFileName(dlg.FileName);
                }
            }
            catch (Exception ex) { StatusText.Text = "Error PNG: " + ex.Message; }
        }

        // ===================== CORRER =====================
        private void Run_Click(object sender, RoutedEventArgs e) => Run();

        private async void Run() => await RunCore();

        // Corre OpenSees+oscalc, navega el WebView2 al reporte y devuelve la ruta del HTML (o null).
        private bool _running, _pendingRun;
        internal int _runCount;   // cuantas corridas empezaron (para comprobar el AutoRun por --ctl)
        private async Task<string> RunCore()
        {   // una sola corrida a la vez: si llega otra mientras corre (AutoRun o F5), se repite UNA vez al terminar
            if (_running) { _pendingRun = true; return null; }
            _running = true;
            try { string r; do { _pendingRun = false; r = await RunCoreInner(); } while (_pendingRun); return r; }
            finally { _running = false; }
        }

        private async Task<string> RunCoreInner()
        {
            try
            {
                _ranOnce = true; _runCount++;
                StatusText.Text = "Corriendo Hekatan OpenSees…";
                var tcl = Path.Combine(_tmp, "model.tcl");
                var html = Path.Combine(_tmp, "model.html");
                File.WriteAllText(tcl, Editor.Text, new System.Text.UTF8Encoding(false));
                var oscalc = Path.Combine(AppContext.BaseDirectory, "oscalc.py");
                var psi = new ProcessStartInfo("python", $"\"{oscalc}\" \"{tcl}\" \"{html}\" --report-only")
                {
                    RedirectStandardError = true,
                    RedirectStandardOutput = true,
                    UseShellExecute = false,
                    CreateNoWindow = true
                };
                psi.Environment["HK_TEMA"] = _dark ? "dark" : "claro";
                psi.Environment["PYTHONIOENCODING"] = "utf-8";
                using var p = Process.Start(psi);
                // la salida estandar TAMBIEN se lee: la DLL escribe avisos en cada paso y, si nadie vacia el tubo (64 KB), Python se queda colgado
                var soTask = p.StandardOutput.ReadToEndAsync();
                var t0 = DateTime.Now;
                var tick = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
                tick.Tick += (ss, ee) => StatusText.Text = "Corriendo Hekatan OpenSees… " + (int)(DateTime.Now - t0).TotalSeconds + " s";
                tick.Start();
                string err;
                try { err = await p.StandardError.ReadToEndAsync(); await p.WaitForExitAsync(); await soTask; }
                finally { tick.Stop(); }
                // el AutoRun NO se apaga nunca ni se retrasa: sigue corriendo ~700 ms despues de dejar de escribir (la guarda _running evita solapes)
                await Web.EnsureCoreWebView2Async();
                if (File.Exists(html))
                    Web.CoreWebView2.Navigate(new Uri(html).AbsoluteUri);
                StatusText.Text = string.IsNullOrWhiteSpace(err) ? "Listo" : "Error de Python/OpenSees (ver consola)";
                if (!string.IsNullOrWhiteSpace(err))
                    StatusText.ToolTip = err;
                return File.Exists(html) ? html : null;
            }
            catch (Exception ex)
            {
                StatusText.Text = "Error: " + ex.Message;
                return null;
            }
        }

        private void Editor_TextChanged(object sender, EventArgs e)
        {
            if (!_noAutoRun && _autoTimer != null && AutoRun != null && AutoRun.IsChecked == true)
            {
                _autoTimer.Stop();    // reinicia el conteo en cada tecla → corre cuando dejas de escribir
                _autoTimer.Start();
            }
        }

        // ===================== INSERTAR SNIPPETS OPENSEES =====================
        private void Insert_Click(object sender, RoutedEventArgs e)
        {
            if (sender is MenuItem mi && mi.Tag is string key && Snippets.TryGetValue(key, out var snip))
                InsertAtCursor(snip);
        }

        private void InsertAtCursor(string text)
        {
            int i = Editor.SelectionStart;
            Editor.Text = Editor.Text.Insert(i, text);
            Editor.SelectionStart = i + text.Length;
            Editor.SelectionLength = 0;
            Editor.Focus();
        }

        // ===================== ARCHIVO =====================
        private void New_Click(object sender, RoutedEventArgs e) { _file = null; Editor.Text = ""; Title = "Hekatan OpenSees"; }

        // Menú Ejemplos: se puebla al arrancar con los .tcl de la carpeta Examples (junto al .exe).
        private void PopulateExamplesMenu()
        {
            try
            {
                string dir = Path.Combine(AppContext.BaseDirectory, "Examples");
                if (!Directory.Exists(dir)) return;
                var files = Directory.GetFiles(dir, "*.tcl");
                if (files.Length == 0) return;
                Array.Sort(files, StringComparer.OrdinalIgnoreCase);
                ExamplesMenu.Items.Clear();
                var cimentaciones = new MenuItem { Header = "Cimentaciones y suelo-estructura" };
                var validaciones = new MenuItem { Header = "Validación (losas)" };
                foreach (var f in files)
                {
                    string nom = Path.GetFileNameWithoutExtension(f);
                    var mi = new MenuItem { Header = nom, Tag = f };
                    mi.Click += Example_Click;
                    // 11, 13, 14 y 15 son de cimentación / interacción suelo-estructura; validacion* son las losas
                    if (nom.StartsWith("11 ") || nom.StartsWith("13 ") || nom.StartsWith("14 ") || nom.StartsWith("15 ")) cimentaciones.Items.Add(mi);
                    else if (nom.StartsWith("validacion", StringComparison.OrdinalIgnoreCase)) validaciones.Items.Add(mi);
                    else ExamplesMenu.Items.Add(mi);
                }
                if (cimentaciones.Items.Count > 0) ExamplesMenu.Items.Add(cimentaciones);
                if (validaciones.Items.Count > 0) ExamplesMenu.Items.Add(validaciones);
            }
            catch { }
        }
        private void Example_Click(object sender, RoutedEventArgs e)
        {
            if (sender is MenuItem mi && mi.Tag is string path && File.Exists(path))
            {
                _file = null;   // es un ejemplo: no sobrescribe el archivo del usuario al Guardar
                _noAutoRun = true;   // se corre una sola vez, aqui: el AutoRun no lo repite
                try { Editor.Text = File.ReadAllText(path); } finally { _noAutoRun = false; }
                Title = "Hekatan OpenSees — ejemplo: " + Path.GetFileNameWithoutExtension(path);
                Run();
            }
        }
        private void Open_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "Script OpenSees (*.tcl)|*.tcl|Todos|*.*" };
            if (dlg.ShowDialog() == true) { _file = dlg.FileName; Editor.Text = File.ReadAllText(_file); Title = "Hekatan OpenSees — " + Path.GetFileName(_file); }
        }

        private void Save_Click(object sender, RoutedEventArgs e) => Save();
        private void Save()
        {
            if (_file == null) { SaveAs_Click(null, null); return; }
            File.WriteAllText(_file, Editor.Text);
            StatusText.Text = "Guardado: " + Path.GetFileName(_file);
        }

        private void SaveAs_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.SaveFileDialog { Filter = "Script OpenSees (*.tcl)|*.tcl", FileName = "modelo.tcl" };
            if (dlg.ShowDialog() == true) { _file = dlg.FileName; File.WriteAllText(_file, Editor.Text); Title = "Hekatan OpenSees — " + Path.GetFileName(_file); }
        }

        private void ExportHtml_Click(object sender, RoutedEventArgs e)
        {
            var src = Path.Combine(_tmp, "model.html");
            if (!File.Exists(src)) { Run(); return; }
            var dlg = new Microsoft.Win32.SaveFileDialog { Filter = "Reporte HTML (*.html)|*.html", FileName = "reporte.html" };
            if (dlg.ShowDialog() == true) File.Copy(src, dlg.FileName, true);
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Close();

        // ===================== EDITAR =====================
        private void Undo_Click(object sender, RoutedEventArgs e) => Editor.Undo();
        private void Redo_Click(object sender, RoutedEventArgs e) => Editor.Redo();
        private void Cut_Click(object sender, RoutedEventArgs e) => Editor.Cut();
        private void Copy_Click(object sender, RoutedEventArgs e) => Editor.Copy();
        private void Paste_Click(object sender, RoutedEventArgs e) => Editor.Paste();
        private void SelectAll_Click(object sender, RoutedEventArgs e) => Editor.SelectAll();

        private void Comment_Click(object sender, RoutedEventArgs e)
        {
            // Comenta/descomenta con '# ' las líneas tocadas por la selección (Tcl)
            var doc = Editor.Document;
            var l1 = doc.GetLineByOffset(Editor.SelectionStart);
            var l2 = doc.GetLineByOffset(Editor.SelectionStart + Editor.SelectionLength);
            int start = l1.Offset, end = l2.EndOffset;
            var lines = doc.GetText(start, end - start).Replace("\r\n", "\n").Split('\n');
            bool allCommented = true;
            foreach (var ln in lines) if (ln.TrimStart().Length > 0 && !ln.TrimStart().StartsWith("#")) { allCommented = false; break; }
            for (int i = 0; i < lines.Length; i++)
            {
                if (lines[i].TrimStart().Length == 0) continue;
                lines[i] = allCommented
                    ? System.Text.RegularExpressions.Regex.Replace(lines[i], @"^(\s*)#\s?", "$1")
                    : System.Text.RegularExpressions.Regex.Replace(lines[i], @"^(\s*)", "$1# ");
            }
            var rep = string.Join("\r\n", lines);
            doc.Replace(start, end - start, rep);
            Editor.Select(start, rep.Length);
        }

        // ===================== AYUDA =====================
        private void HelpRef_Click(object sender, RoutedEventArgs e) =>
            Process.Start(new ProcessStartInfo("https://opensees.berkeley.edu/wiki/index.php/Command_Manual") { UseShellExecute = true });

        private void About_Click(object sender, RoutedEventArgs e) =>
            MessageBox.Show("Hekatan OpenSees\n\nEditor estilo Hekatan Lab que renderiza scripts de OpenSees (Tcl).\nMotor: Hekatan OpenSees (DLL de Petracca y Camata, con ASDShellQ4 y ASDConcrete3D) cargada en un intérprete Tcl.",
                "Acerca de", MessageBoxButton.OK, MessageBoxImage.Information);

        // ===================== SNIPPETS OPENSEES =====================
        private static readonly Dictionary<string, string> Snippets = new()
        {
            ["wipe"] = "wipe\n",
            ["model2d"] = "model basic -ndm 2 -ndf 3\n",
            ["model3d"] = "model basic -ndm 3 -ndf 6\n",
            ["node"] = "node 1 0.0 0.0\n",
            ["fix"] = "fix 1 1 1 1\n",
            ["mass"] = "mass 1 0.0 0.0 0.0\n",
            ["diaph"] = "rigidDiaphragm 3 $masterNode $slaveNodes\n",
            ["gtLinear"] = "geomTransf Linear 1\n",
            ["gtPDelta"] = "geomTransf PDelta 1\n",
            ["gtCoro"] = "geomTransf Corotational 1\n",
            ["matElastic"] = "uniaxialMaterial Elastic 1 200000000.0\n",
            ["matSteel02"] = "uniaxialMaterial Steel02 1 $Fy $E $b 18.0 0.925 0.15\n",
            ["matConc02"] = "uniaxialMaterial Concrete02 1 $fpc $epsc0 $fpcu $epsU $lambda $ft $Ets\n",
            ["ndElastic"] = "nDMaterial ElasticIsotropic 1 200000000.0 0.3\n",
            ["secElastic"] = "section Elastic 1 $E $A $Iz\n",
            ["secPlate"] = "section ElasticMembranePlateSection 1 $E $nu $h 0.0\n",
            ["secFiber"] = "section Fiber 1 {\n    # patch rect / layer straight ...\n}\n",
            ["elTruss"] = "element truss 1 $n1 $n2 $A $matTag\n",
            ["elEBC"] = "element elasticBeamColumn 1 $n1 $n2 $A $E $Iz $transfTag\n",
            ["elFBC"] = "element forceBeamColumn 1 $n1 $n2 $transfTag $integrTag\n",
            ["elZL"] = "element zeroLength 1 $n1 $n2 -mat 1 -dir 1\n",
            ["elQuad"] = "element quad 1 $n1 $n2 $n3 $n4 $thick PlaneStress 1\n",
            ["elMITC4"] = "element ShellMITC4 1 $n1 $n2 $n3 $n4 $secTag\n",
            ["elDKGQ"] = "element ShellDKGQ 1 $n1 $n2 $n3 $n4 $secTag\n",
            ["elDKGT"] = "element ShellDKGT 1 $n1 $n2 $n3 $secTag\n",
            ["elBrick"] = "element stdBrick 1 $n1 $n2 $n3 $n4 $n5 $n6 $n7 $n8 $matTag\n",
            ["tsLinear"] = "timeSeries Linear 1\n",
            ["tsPath"] = "timeSeries Path 1 -dt 0.01 -filePath datos.txt -factor 1.0\n",
            ["patPlain"] = "pattern Plain 1 1 {\n    load 2 0.0 -10.0 0.0\n}\n",
            ["load"] = "load 2 0.0 -10.0 0.0\n",
            ["eleLoad"] = "eleLoad -ele 1 -type -beamUniform -10.0 0.0\n",
            ["sp"] = "sp 1 1 0.01\n",
            ["anStatic"] = "# --- Análisis estático lineal ---\nsystem BandSPD\nnumberer RCM\nconstraints Plain\nintegrator LoadControl 1.0\nalgorithm Linear\nanalysis Static\nanalyze 1\n",
            ["anModal"] = "# --- Análisis modal ---\nset lambda [eigen 3]\nset pi 3.141592653589793\nforeach l $lambda { puts \"T = [expr {2.0*$pi/sqrt($l)}] s\" }\n",
            ["anDynamic"] = "# --- Análisis dinámico (Newmark) ---\nconstraints Plain\nnumberer RCM\nsystem BandGeneral\nalgorithm Newton\nintegrator Newmark 0.5 0.25\nanalysis Transient\nanalyze 1000 0.01\n",
            ["analyze"] = "analyze 1\n",
            ["resDisp"] = "puts \"uy = [nodeDisp 2 2]\"\n",
            ["resCalcpad"] = "puts \"HEKATAN:uy=[nodeDisp 2 2]\"\n",
            ["resReact"] = "reactions\nputs \"R = [nodeReaction 1]\"\n",
            ["recNode"] = "recorder Node -file disp.out -node 2 -dof 1 2 3 disp\n",
            ["recEle"] = "recorder Element -file forces.out -ele 1 forces\n",
            ["resModal"] = "set lambda [eigen 3]\nputs \"lambdas = $lambda\"\n",
            // --- Gráficas MATLAB embebidas (líneas '#' = comentario para OpenSees) ---
            ["dibujar"] = "## Dibujo 2D/3D (como Hekatan LISP)\n#dibujar\n# modelo\n# capa DIBUJO\n# linea 0 0 0  5 0 0\n#enddibujar\n",
            ["gfxPlotly"] = "#gfx\n# var x=linspace(0,10,50);\n# plotlyPlot(x, x.map(Math.sin), 'Seno (Plotly, opcional)', 'x', 'y');\n#endgfx\n",
            ["gfxBlock"] = "#gfx\n# figure(); var x=linspace(0,10,50);\n# plot(x, x.map(Math.sin), 'r-'); title('demo'); xlabel('x'); ylabel('y'); grid('on');\n#endgfx\n",
            ["gfxPlot"] = "# figure(); plot(x, y, 'r-'); title('título'); xlabel('x'); ylabel('y');\n",
            ["gfxSurf"] = "# figure(); var g=linspace(-3,3,24); var m=meshgrid(g,g);\n# surf(m[0], m[1], Z); title('superficie 3D');\n",
            ["gfxBar"] = "# figure(); bar([1,2,3,4], [3,7,2,5]); title('bar');\n",
        };

        private const string Sample =
            "# Viga en voladizo 2D — ejemplo OpenSees\n" +
            "wipe\n" +
            "model basic -ndm 2 -ndf 3\n" +
            "node 1 0 0\n" +
            "node 2 5 0\n" +
            "fix 1 1 1 1\n" +
            "geomTransf Linear 1\n" +
            "element elasticBeamColumn 1 1 2 0.01 210000000 0.00008333 1\n" +
            "timeSeries Linear 1\n" +
            "pattern Plain 1 1 { load 2 0 -10 0 }\n" +
            "system BandSPD\n" +
            "numberer RCM\n" +
            "constraints Plain\n" +
            "integrator LoadControl 1.0\n" +
            "algorithm Linear\n" +
            "analysis Static\n" +
            "analyze 1\n" +
            "puts \"uy = [expr {[nodeDisp 2 2]*1000}] mm\"\n" +
            "puts \"HEKATAN:uy_mm=[expr {[nodeDisp 2 2]*1000}]\"\n";
    }

    // Comando mínimo para los KeyBinding (F5, Ctrl+S)
    internal sealed class RelayCommand : ICommand
    {
        private readonly Action<object> _exec;
        public RelayCommand(Action<object> exec) => _exec = exec;
        public bool CanExecute(object parameter) => true;
        public void Execute(object parameter) => _exec(parameter);
        public event EventHandler CanExecuteChanged { add { } remove { } }
    }
}
