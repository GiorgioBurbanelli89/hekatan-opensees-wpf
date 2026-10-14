using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using ICSharpCode.AvalonEdit.CodeCompletion;
using ICSharpCode.AvalonEdit.Document;
using ICSharpCode.AvalonEdit.Editing;
using ICSharpCode.AvalonEdit.Rendering;

namespace HekatanOpenSees
{
    // Editor AvalonEdit (igual que Hekatan Lab): números de línea, colores por tema y autocompletado.
    public partial class MainWindow
    {
        private TclColorizer _colorizer;
        private CompletionWindow _completion;

        private void SetupEditor()
        {
            Editor.ShowLineNumbers = true;
            Editor.Options.EnableHyperlinks = false;
            Editor.Options.ConvertTabsToSpaces = true;
            Editor.Options.IndentationSize = 4;
            _colorizer = new TclColorizer();
            Editor.TextArea.TextView.LineTransformers.Add(_colorizer);
            Editor.TextArea.TextEntered += Editor_TextEntered;
            Editor.TextArea.TextEntering += Editor_TextEntering;
            Editor.TextArea.PreviewKeyDown += (s, e) =>
            {
                if (e.Key == Key.Space && Keyboard.Modifiers == ModifierKeys.Control) { ShowCompletion(true); e.Handled = true; }
                else if (e.Key == Key.Q && Keyboard.Modifiers == ModifierKeys.Control) { Comment_Click(this, null); e.Handled = true; }
            };
            ApplyEditorTheme();
        }

        // Colores del editor según el tema (oscuro | claro "oro"), los mismos tonos de Hekatan Lab.
        private void ApplyEditorTheme()
        {
            if (_colorizer == null) return;
            _colorizer.Dark = _dark;
            Editor.LineNumbersForeground = (Brush)FindResource("ThemeTextMuted");
            Editor.Foreground = (Brush)FindResource("ThemeText");
            Editor.Background = (Brush)FindResource("ThemeEditorBg");
            Editor.TextArea.TextView.Redraw();
        }

        private void Editor_TextEntering(object sender, TextCompositionEventArgs e)
        {
            if (e.Text.Length > 0 && _completion != null && !char.IsLetterOrDigit(e.Text[0]) && e.Text[0] != '_' && e.Text[0] != '-')
                _completion.CompletionList.RequestInsertion(e);
        }

        private void Editor_TextEntered(object sender, TextCompositionEventArgs e)
        {
            if (e.Text.Length == 1 && (char.IsLetter(e.Text[0]) || e.Text[0] == '-')) ShowCompletion(false);
        }

        // Palabra que se está escribiendo (a la izquierda del cursor)
        private (int start, string word) CurrentWord()
        {
            int off = Editor.CaretOffset;
            int i = off;
            while (i > 0)
            {
                char c = Editor.Document.GetCharAt(i - 1);
                if (char.IsLetterOrDigit(c) || c == '_' || c == '-') i--; else break;
            }
            return (i, Editor.Document.GetText(i, off - i));
        }

        private void ShowCompletion(bool force)
        {
            if (_completion != null) return;
            var (start, word) = CurrentWord();
            if (!force && word.Length < 2) return;
            var line = Editor.Document.GetLineByOffset(Editor.CaretOffset);
            string before = Editor.Document.GetText(line.Offset, start - line.Offset);
            bool inComment = before.TrimStart().StartsWith("#");
            var src = inComment ? TclWords.Matlab : (before.Trim().Length == 0 ? TclWords.Commands : TclWords.Commands.Concat(TclWords.Options));
            var items = src.Distinct().Where(w => w.StartsWith(word, StringComparison.OrdinalIgnoreCase) && w.Length > word.Length)
                           .OrderBy(w => w, StringComparer.OrdinalIgnoreCase).Take(60).ToList();
            if (items.Count == 0) return;
            _completion = new CompletionWindow(Editor.TextArea);
            _completion.StartOffset = start;
            _completion.Background = (Brush)FindResource("ThemePanelBg");
            _completion.Foreground = (Brush)FindResource("ThemeText");
            foreach (var w in items) _completion.CompletionList.CompletionData.Add(new WordData(w, TclWords.Doc(w)));
            _completion.Closed += (s, e) => _completion = null;
            _completion.Show();
        }

        private sealed class WordData : ICompletionData
        {
            private readonly string _t, _d;
            public WordData(string t, string d) { _t = t; _d = d; }
            public System.Windows.Media.ImageSource Image => null;
            public string Text => _t;
            public object Content => _t;
            public object Description => _d;
            public double Priority => 0;
            public void Complete(TextArea ta, ISegment seg, EventArgs e) => ta.Document.Replace(seg, _t);
        }
    }

    // Resaltado por líneas: comentarios (#), títulos (##), directivas de reporte (#gfx…), comandos OpenSees, números, cadenas, llaves.
    public sealed class TclColorizer : DocumentColorizingTransformer
    {
        public bool Dark = true;
        private static readonly Regex Directive = new Regex(@"^\s*#(title|gfx|endgfx|hide|show|plot|values|cp|endcp|table|html|md|pagebreak)\b", RegexOptions.Compiled);
        private static readonly Regex Num = new Regex(@"(?<![\w.])[-+]?\d+(\.\d+)?([eE][-+]?\d+)?(?![\w])", RegexOptions.Compiled);
        private static readonly Regex Str = new Regex("\"[^\"\\n]*\"", RegexOptions.Compiled);
        private static readonly Regex Word = new Regex(@"^\s*([A-Za-z_][\w:.]*)", RegexOptions.Compiled);
        private static readonly Regex Opt = new Regex(@"(?<=\s)-[A-Za-z]\w*", RegexOptions.Compiled);
        private static readonly Regex Var = new Regex(@"\$\w+|\[[^\]\n]*\]", RegexOptions.Compiled);

        private Brush B(string dark, string light) { var b = (SolidColorBrush)new BrushConverter().ConvertFromString(Dark ? dark : light); b.Freeze(); return b; }

        protected override void ColorizeLine(DocumentLine line)
        {
            string t = CurrentContext.Document.GetText(line);
            int o = line.Offset;
            void Paint(int a, int len, Brush fg, bool bold = false, bool italic = false)
            {
                if (len <= 0) return;
                ChangeLinePart(o + a, o + a + len, el =>
                {
                    el.TextRunProperties.SetForegroundBrush(fg);
                    if (bold || italic)
                        el.TextRunProperties.SetTypeface(new Typeface(el.TextRunProperties.Typeface.FontFamily,
                            italic ? FontStyles.Italic : FontStyles.Normal, bold ? FontWeights.Bold : FontWeights.Normal,
                            FontStretches.Normal));
                });
            }
            var trim = t.TrimStart();
            int ind = t.Length - trim.Length;
            if (trim.StartsWith("#"))
            {
                if (trim.StartsWith("##")) Paint(ind, t.Length - ind, B("#E6C463", "#8A6A00"), bold: true);          // ## título del reporte
                else if (Directive.IsMatch(t)) Paint(ind, t.Length - ind, B("#E5382B", "#C0392B"), bold: true);       // #gfx #plot …
                else Paint(ind, t.Length - ind, B("#7F9F6A", "#4F7A2E"), italic: true);                             // # comentario (o código de #gfx)
                return;
            }
            foreach (Match m in Var.Matches(t)) Paint(m.Index, m.Length, B("#C9A7F0", "#7A3FB0"));
            foreach (Match m in Num.Matches(t)) Paint(m.Index, m.Length, B("#8EC5FF", "#0B5CAD"));
            foreach (Match m in Opt.Matches(t)) Paint(m.Index, m.Length, B("#6FD6A0", "#157A4A"));
            foreach (Match m in Str.Matches(t)) Paint(m.Index, m.Length, B("#E69F6B", "#A0522D"));
            var w = Word.Match(t);
            if (w.Success && TclWords.Commands.Contains(w.Groups[1].Value)) Paint(w.Groups[1].Index, w.Groups[1].Length, B("#E6C463", "#8A6A00"), bold: true);
            for (int i = 0; i < t.Length; i++) if (t[i] == '{' || t[i] == '}') Paint(i, 1, B("#C9C0AD", "#6B5E45"), bold: true);
        }
    }

    public static class TclWords
    {
        public static readonly HashSet<string> Commands = new HashSet<string>(StringComparer.Ordinal)
        {
            "wipe","wipeAnalysis","model","node","fix","fixX","fixY","fixZ","mass","equalDOF","rigidDiaphragm","rigidLink","geomTransf",
            "uniaxialMaterial","nDMaterial","section","patch","layer","fiber","element","timeSeries","pattern","load","eleLoad","sp","imposedMotion",
            "system","numberer","constraints","integrator","algorithm","analysis","analyze","test","eigen","modalProperties","responseSpectrum",
            "recorder","record","nodeDisp","nodeVel","nodeAccel","nodeReaction","nodeEigenvector","nodeCoord","eleResponse","eleForce","basicForce",
            "getNodeTags","getEleTags","eleNodes","reactions","remove","region","damping","rayleigh","loadConst","setTime","getTime","reset",
            "puts","set","expr","for","foreach","while","if","else","elseif","proc","return","source","format","list","lindex","llength","lappend",
            "block2D","block3D","mesh","build","getEigenvalues","printA","print","database","save","restore","sensitivityAlgorithm","initialize","updateMaterialStage",
        };

        public static readonly string[] Options =
        {
            "-ndm","-ndf","-mass","-section","-rho","-iter","-nodes","-time","-file","-nodeRange","-dof","-doRayleigh","-genBandArpack","-fullGenLapack","-symmBandLapack",
            "-beamUniform","-beamPoint","-const","-factor","-fx","-values","-time","-dt","-endTime","-initial","-NodeRange","-ele","-region",
            "Linear","PDelta","Corotational","Plain","Static","Transient","Newmark","LoadControl","DisplacementControl","Newton","ModifiedNewton","BandGeneral","BandSPD",
            "ProfileSPD","UmfPack","SparseGeneral","FullGeneral","RCM","AMD","Plain","Penalty","Lagrange","Transformation","NormDispIncr","NormUnbalance",
            "elasticBeamColumn","dispBeamColumn","forceBeamColumn","truss","corotTruss","zeroLength","twoNodeLink","ShellMITC4","ShellDKGQ","ShellDKGT","ShellNLDKGQ",
            "ASDShellQ4","ASDShellT3","quad","tri31","stdBrick","bbarBrick","SSPbrick","FourNodeQuad","ElasticTimoshenkoBeam","elasticBeamColumn",
            "Elastic","Steel01","Steel02","Concrete01","Concrete02","Concrete04","ElasticIsotropic","ElasticMembranePlateSection","PlateFiber","Fiber","ASDConcrete3D","ASDPlasticMaterial3D",
            "PlaneStress","PlaneStrain","PressureIndependMultiYield","J2Plasticity","Hardening","Parallel","Series",
        };

        // Funciones de Hekatan Lab que se pueden escribir dentro de los # comentarios de un bloque #gfx
        public static readonly string[] Matlab =
        {
            "figure","plot","plot3","surf","mesh","contour","contourf","bar","barh","scatter","scatter3","hist","pie","fill","patch","quiver","quiver3",
            "title","xlabel","ylabel","zlabel","legend","grid","axis","hold","subplot","colormap","colorbar","datacursor","text","line","semilogx","semilogy","loglog",
            "linspace","meshgrid","zeros","ones","eye","size","length","sum","cumsum","max","min","abs","sqrt","sin","cos","tan","exp","log","pi","floor","ceil","round",
            "eig","inv","det","norm","diag","transpose","trace","rank","solve","interp1","polyfit","polyval","trapz","diff","mean","std",
            "uy_mm","giro_rad","Math.sin","Math.cos","Math.exp","Math.sqrt","Math.PI",
        };

        public static string Doc(string w)
        {
            switch (w)
            {
                case "node": return "node tag x y (z) [-mass ...]";
                case "fix": return "fix nodeTag  ux uy (uz rx ry rz) — 1 = restringido";
                case "element": return "element tipo tag nodos... propiedades";
                case "pattern": return "pattern Plain tag tsTag { load nodo fx fy ... }";
                case "analyze": return "analyze numPasos (dt)";
                case "eigen": return "eigen (-fullGenLapack) numModos — devuelve λ = ω²";
                case "ASDShellQ4": return "ASDShellQ4 (Petracca y Camata): element ASDShellQ4 tag n1 n2 n3 n4 secTag";
                case "ShellMITC4": return "element ShellMITC4 tag n1 n2 n3 n4 secTag";
                case "nodeDisp": return "nodeDisp nodo (gdl) — desplazamiento";
                case "plot": return "plot(x, y, 'r-') — gráfica 2D de Hekatan Lab";
                case "surf": return "surf(X, Y, Z) — superficie 3D orbitable";
                case "datacursor": return "datacursor('texto') — datatip al pasar el cursor";
                default: return Commands.Contains(w) ? "Comando OpenSees: " + w : w;
            }
        }
    }
}
