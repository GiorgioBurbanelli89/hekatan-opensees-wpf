// Hekatan OpenSees — Plotly dentro de los bloques #gfx (igual que Hekatan Lab: plot/surf/bar con hover, zoom y giro 3D)
// Uso en un bloque #gfx:   # plotly([{x:[1,2,3], y:[4,5,6], type:'scatter'}], {title:'mi grafica'});
//                          # plotlyPlot(x, w, 'Flecha', 'x [m]', 'w [mm]');   # plotlySurf(gx, gy, Z, 'Z = f(x,y)');
(function () {
  var n = 0;
  function tema() {
    var d = !!window.HK_DARK, bg = d ? "#1a1712" : "#FFFDF6", fg = d ? "#e8e2d4" : "#333333", gr = d ? "#3a3226" : "#dddddd";
    return { bg: bg, fg: fg, gr: gr };
  }
  function host() {
    var div = document.createElement("div"); div.id = "hkpl" + (n++);
    div.style.cssText = "width:640px;max-width:100%;height:420px;margin:6px 0;border:1px solid " + tema().gr + ";border-radius:6px;display:inline-block";
    var s = document.currentScript; (s && s.parentNode ? s.parentNode : document.body).insertBefore(div, s || null);
    return div;
  }
  function base(layout) {
    var t = tema(), ax = { color: t.fg, gridcolor: t.gr, zerolinecolor: t.gr, linecolor: t.fg };
    var L = { paper_bgcolor: t.bg, plot_bgcolor: t.bg, font: { color: t.fg, family: "Segoe UI" }, margin: { l: 56, r: 20, t: 40, b: 46 },
              xaxis: ax, yaxis: Object.assign({}, ax), hovermode: "closest" };
    L.scene = { bgcolor: t.bg, xaxis: Object.assign({}, ax), yaxis: Object.assign({}, ax), zaxis: Object.assign({}, ax) };
    layout = layout || {};
    Object.keys(layout).forEach(function (k) {
      L[k] = (typeof layout[k] === "object" && !Array.isArray(layout[k]) && L[k]) ? Object.assign({}, L[k], layout[k]) : layout[k];
    });
    return L;
  }
  window.plotly = function (traces, layout, config) {
    if (!window.Plotly) { document.currentScript.insertAdjacentHTML("beforebegin", "<p class='oserr'>Plotly no está cargado</p>"); return; }
    var div = host();
    Plotly.newPlot(div, traces, base(layout), Object.assign({ responsive: true, displaylogo: false }, config || {}));
    return div;
  };
  window.plotlyPlot = function (x, y, title, xl, yl) {
    return window.plotly([{ x: x, y: y, type: "scatter", mode: "lines+markers", line: { color: "#E5382B", width: 2.4 }, marker: { size: 5 } }],
      { title: title || "", xaxis: { title: xl || "" }, yaxis: { title: yl || "" } });
  };
  window.plotlyBar = function (x, y, title) { return window.plotly([{ x: x, y: y, type: "bar", marker: { color: "#E6C463" } }], { title: title || "" }); };
  window.plotlySurf = function (x, y, Z, title) {
    return window.plotly([{ x: x, y: y, z: Z, type: "surface", colorscale: "Jet" }], { title: title || "" });
  };
})();
