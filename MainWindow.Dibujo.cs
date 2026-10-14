using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Windows;
using ICSharpCode.AvalonEdit.Document;

namespace HekatanOpenSees
{
    // Lo que se dibuja con el cursor en la ventana 2D/3D del reporte se escribe en el guion como `# linea x y z x y z`
    // dentro de #dibujar … #enddibujar (comentarios para OpenSees), y se guarda en DXF y DWG como Hekatan LISP.
    public partial class MainWindow
    {
        private readonly List<string> _dibLineas = new List<string>();
        private bool _noAutoRun;

        private void HookDibujo()
        {
            Web.CoreWebView2.WebMessageReceived += (s, e) =>
            {
                try
                {
                    using var doc = JsonDocument.Parse(e.TryGetWebMessageAsString());
                    var r = doc.RootElement;
                    switch (r.GetProperty("tipo").GetString())
                    {
                        case "dibujo-add": DibujoAgregar(r.GetProperty("linea").GetString()); break;
                        case "dibujo-undo": DibujoDeshacer(); break;
                        case "dibujo-guardar": DibujoGuardar(r); break;
                        case "dibujo-modelo": DibujoModelo(r.GetProperty("tcl").GetString()); break;
                    }
                }
                catch (Exception ex) { StatusText.Text = "Dibujo: " + ex.Message; }
            };
        }

        // Inserta `# <linea>` justo antes de #enddibujar (el ultimo bloque); sin bloque, lo crea al final.
        private void DibujoAgregar(string linea)
        {
            var d = Editor.Document;
            DocumentLine fin = null;
            for (var l = d.GetLineByNumber(d.LineCount); l != null; l = l.PreviousLine)
                if (d.GetText(l).TrimStart().StartsWith("#enddibujar", StringComparison.OrdinalIgnoreCase)) { fin = l; break; }
            _noAutoRun = true;
            try
            {
                string nl = Environment.NewLine, txt = "# " + linea + nl;
                if (fin != null) d.Insert(fin.Offset, txt);
                else d.Insert(d.TextLength, nl + "## Dibujo" + nl + "#dibujar" + nl + txt + "#enddibujar" + nl);
            }
            finally { _noAutoRun = false; }
            _dibLineas.Add(linea);
            StatusText.Text = "Dibujo: # " + linea;
        }

        // Pone el modelo OpenSees armado desde el dibujo (nudos, barras, cascaras) en el cursor del editor.
        private void DibujoModelo(string tcl)
        {
            string nl = Environment.NewLine;
            _noAutoRun = true;
            try { Editor.Document.Insert(Editor.CaretOffset, nl + tcl.Replace("\n", nl) + nl); }
            finally { _noAutoRun = false; }
            StatusText.Text = "Modelo OpenSees insertado en el cursor del editor";
        }

        private void DibujoDeshacer()
        {
            if (_dibLineas.Count == 0) return;
            string linea = "# " + _dibLineas[_dibLineas.Count - 1];
            _dibLineas.RemoveAt(_dibLineas.Count - 1);
            var d = Editor.Document;
            for (var l = d.GetLineByNumber(d.LineCount); l != null; l = l.PreviousLine)
                if (d.GetText(l).Trim() == linea.Trim())
                {
                    _noAutoRun = true;
                    try { d.Remove(l.TotalLength == 0 ? l.Offset : l.Offset, l.TotalLength); } finally { _noAutoRun = false; }
                    break;
                }
        }

        private void DibujoGuardar(JsonElement r)
        {
            string fmt = r.GetProperty("fmt").GetString(), nombre = r.TryGetProperty("nombre", out var n) ? n.GetString() : "dibujo";
            var dlg = new Microsoft.Win32.SaveFileDialog
            {
                FileName = nombre + "." + fmt,
                Filter = fmt == "dwg" ? "DWG (AutoCAD 2018)|*.dwg" : "DXF (AutoCAD R12)|*.dxf"
            };
            if (dlg.ShowDialog() != true) return;
            try
            {
                if (fmt == "dxf") File.WriteAllText(dlg.FileName, r.GetProperty("dxf").GetString(), Encoding.ASCII);
                else File.WriteAllBytes(dlg.FileName, DwgConNode(r.GetProperty("json").GetString()));
                StatusText.Text = "Dibujo guardado: " + dlg.FileName;
            }
            catch (Exception ex) { StatusText.Text = "No se pudo guardar: " + ex.Message; MessageBox.Show(ex.Message, "Guardar dibujo"); }
        }

        private static string NodeExe()
        {
            foreach (var d in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
            {
                try { var p = Path.Combine(d.Trim('"'), "node.exe"); if (File.Exists(p)) return p; } catch { }
            }
            var pf = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "nodejs", "node.exe");
            return File.Exists(pf) ? pf : null;
        }

        // JSON de acadrust (pares DXF) -> bytes .dwg con acadrust-wasm en Node: el MISMO escritor que usa Hekatan LISP.
        private static byte[] DwgConNode(string json)
        {
            var node = NodeExe() ?? throw new InvalidOperationException("DWG: hace falta Node.js (acadrust-wasm corre en Node); guarda en DXF");
            var pkg = Path.Combine(AppContext.BaseDirectory, "dwg", "acadrust_wasm.js");
            if (!File.Exists(pkg)) throw new InvalidOperationException("DWG: falta dwg/acadrust_wasm.js junto al programa (pkg-node de acadrust-wasm)");
            var tmp = Path.Combine(Path.GetTempPath(), "hkos_dwg_" + Environment.ProcessId);
            Directory.CreateDirectory(tmp);
            string fj = Path.Combine(tmp, "d.json"), fo = Path.Combine(tmp, "d.dwg");
            File.WriteAllText(fj, json, new UTF8Encoding(false));
            if (File.Exists(fo)) File.Delete(fo);
            var psi = new ProcessStartInfo(node) { UseShellExecute = false, CreateNoWindow = true, RedirectStandardError = true, RedirectStandardOutput = true };
            psi.ArgumentList.Add("-e");
            psi.ArgumentList.Add("const m=require(process.argv[1]);const fs=require('fs');fs.writeFileSync(process.argv[3],m.write_dwg_bytes(fs.readFileSync(process.argv[2],'utf8')))");
            psi.ArgumentList.Add(pkg); psi.ArgumentList.Add(fj); psi.ArgumentList.Add(fo);
            using var p = Process.Start(psi);
            var te = p.StandardError.ReadToEndAsync(); var to = p.StandardOutput.ReadToEndAsync();
            if (!p.WaitForExit(60000)) { try { p.Kill(true); } catch { } throw new TimeoutException("DWG: Node no terminó"); }
            if (!File.Exists(fo)) throw new InvalidOperationException("DWG: " + (te.Result ?? "").Trim());
            return File.ReadAllBytes(fo);
        }
    }
}
