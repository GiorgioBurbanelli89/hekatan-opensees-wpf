// Hekatan OpenSees — la GRIETA animada (como el ejemplo 26 de Hekatan Lab): malla Q4 deformada, coloreada por el daño a tracción d,
// con Reproducir/Pausa, control de cuadro, factor de deformación y datatip al pasar el cursor. Cada cuadro = un paso del análisis.
// «Solo animación» (botón, F11 o Esc para salir) deja en pantalla únicamente la gráfica, a todo el tamaño de la ventana.
(function () {
  "use strict";
  var GR = window.HKGRIETA = {};
  var actual = null;
  function jet(t) {                                   // jet 0..1 (el de Hekatan Lab)
    t = Math.max(0, Math.min(1, t));
    var r = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 3))), g = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 2))), b = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 1)));
    return "rgb(" + Math.round(255 * r) + "," + Math.round(255 * g) + "," + Math.round(255 * b) + ")";
  }
  GR.solo = function (on) { if (actual) actual.solo(on); };
  GR.mount = function (id, D) {
    var root = document.getElementById(id); if (!root) return;
    var W0 = D.w || 760, H0 = D.h || 420, W = W0, H = H0, N = D.nodes, Q = D.quads, F = D.frames, dmax = D.dmax || 0.95;
    root.className = "hkgr";
    root.innerHTML = '<canvas width="' + W + '" height="' + H + '"></canvas><div class="hkgr-tip"></div>' +
      '<div class="hkgr-bar"><button class="pl">▶ Reproducir</button><input type="range" min="0" max="' + (F.length - 1) + '" value="0" step="1"/>' +
      '<label>deformación ×<input class="sf" type="number" value="' + (D.sf || 40) + '" min="0" step="10"/></label>' +
      '<button class="so" title="Solo la animación a pantalla completa (F11; Esc para salir)">⛶ Solo animación</button></div><div class="hkgr-st"></div>';
    var cv = root.querySelector("canvas"), ctx = cv.getContext("2d"), tip = root.querySelector(".hkgr-tip"), pl = root.querySelector(".pl"),
        rg = root.querySelector("input[type=range]"), sfI = root.querySelector(".sf"), st = root.querySelector(".hkgr-st"), so = root.querySelector(".so");
    var xs = N.map(function (p) { return p[0]; }), ys = N.map(function (p) { return p[1]; });
    var x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs), y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    var pad = 36, sc = 1, ox = 0, cur = 0, timer = null, hover = -1, esSolo = false;
    function layout() {                               // la malla centrada en el lienzo, con sitio para la barra de color
      var aw = W - 2 * pad - 90, ah = H - 2 * pad;
      sc = Math.min(aw / (x1 - x0), ah / (y1 - y0)); ox = pad + (aw - (x1 - x0) * sc) / 2;
    }
    function px(p) { return [ox + (p[0] - x0) * sc, H - pad - (p[1] - y0) * sc]; }
    function dark() { return !!window.HK_DARK; }
    function pintar() {
      var f = F[cur], k = +sfI.value || 0, bg = dark() ? "#1a1712" : "#FFFDF6", fg = dark() ? "#e8e2d4" : "#171310", fs = Math.max(11, Math.round(W / 70));
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
      var P = N.map(function (p, i) { return px([p[0] + k * f.u[2 * i], p[1] + k * f.u[2 * i + 1]]); });
      for (var e = 0; e < Q.length; e++) {
        var q = Q[e], d = f.d[e];
        ctx.beginPath(); for (var j = 0; j < 4; j++) { var p = P[q[j] - 1]; if (j) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); } ctx.closePath();
        ctx.fillStyle = jet(d / dmax); ctx.fill();
        ctx.strokeStyle = e === hover ? fg : (dark() ? "rgba(255,255,255,.12)" : "rgba(0,0,0,.18)"); ctx.lineWidth = e === hover ? 2 : 0.4; ctx.stroke();
      }
      var bw = Math.max(16, W / 48), bx = W - pad - 60 * (fs / 11), by = pad, bh = H - 2 * pad;     // barra de color
      for (var i = 0; i < 40; i++) { ctx.fillStyle = jet(1 - i / 39); ctx.fillRect(bx, by + i * bh / 40, bw, bh / 40 + 1); }
      ctx.strokeStyle = fg; ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh); ctx.fillStyle = fg; ctx.font = fs + "px Segoe UI"; ctx.textBaseline = "middle";
      [0, 0.25, 0.5, 0.75, 1].forEach(function (t) { var yy = by + bh * (1 - t); ctx.textAlign = "left"; ctx.fillText((t * dmax).toFixed(2), bx + bw + 6, yy); ctx.beginPath(); ctx.moveTo(bx + bw, yy); ctx.lineTo(bx + bw + 3, yy); ctx.stroke(); });
      ctx.save(); ctx.translate(bx - 8, by + bh / 2); ctx.rotate(-Math.PI / 2); ctx.textAlign = "center"; ctx.fillText("daño a tracción d", 0, 0); ctx.restore();
      var dm = Math.max.apply(null, f.d), nd = f.d.filter(function (v) { return v > 0.5; }).length;
      var txt = "cuadro " + (cur + 1) + "/" + F.length + " · s = " + f.s + (f.ux != null ? " · u coronación = " + f.ux + " mm" : "") + " · d máx = " + dm.toFixed(2) + " · elementos con d > 0.5: " + nd;
      st.textContent = txt;
      if (esSolo) { ctx.textAlign = "left"; ctx.font = "bold " + Math.round(fs * 1.25) + "px Segoe UI"; ctx.fillStyle = fg; ctx.fillText(txt, pad, pad / 2 + 4); }
    }
    function ir(i) { cur = Math.max(0, Math.min(F.length - 1, i)); rg.value = cur; pintar(); }
    function play() {
      if (timer) { clearInterval(timer); timer = null; pl.textContent = "▶ Reproducir"; return; }
      if (cur >= F.length - 1) cur = 0;
      pl.textContent = "⏸ Pausa";
      timer = setInterval(function () { if (cur >= F.length - 1) { clearInterval(timer); timer = null; pl.textContent = "▶ Reproducir"; return; } ir(cur + 1); }, D.ms || 120);
    }
    function ajustarSolo() {                          // en pantalla completa el lienzo toma TODA la ventana menos la barra
      var bar = root.querySelector(".hkgr-bar").getBoundingClientRect().height + 6;
      W = Math.max(400, window.innerWidth); H = Math.max(300, window.innerHeight - bar - 4);
      cv.width = W; cv.height = H; layout(); pintar();
    }
    function solo(on) {
      if (on === undefined) on = !esSolo;
      if (on === esSolo) return;
      esSolo = on; document.documentElement.classList.toggle("hkgr-solo", on); so.textContent = on ? "✕ Salir (Esc)" : "⛶ Solo animación";
      if (on) { ajustarSolo(); window.addEventListener("resize", ajustarSolo); }
      else { window.removeEventListener("resize", ajustarSolo); W = W0; H = H0; cv.width = W; cv.height = H; layout(); pintar(); }
    }
    pl.onclick = play; so.onclick = function () { solo(); };
    window.addEventListener("keydown", function (e) { if (e.key === "F11") { e.preventDefault(); solo(); } else if (e.key === "Escape" && esSolo) solo(false); else if (e.key === " " && esSolo) { e.preventDefault(); play(); } });
    rg.oninput = function () { ir(+rg.value); };
    sfI.onchange = pintar;
    cv.onmousemove = function (ev) {
      var r = cv.getBoundingClientRect(), sx = (ev.clientX - r.left) * W / r.width, sy = (ev.clientY - r.top) * H / r.height, f = F[cur], k = +sfI.value || 0, best = -1;
      for (var e = 0; e < Q.length; e++) {
        var q = Q[e], cx = 0, cy = 0; for (var j = 0; j < 4; j++) { var i = q[j] - 1, p = px([N[i][0] + k * f.u[2 * i], N[i][1] + k * f.u[2 * i + 1]]); cx += p[0] / 4; cy += p[1] / 4; }
        if ((cx - sx) * (cx - sx) + (cy - sy) * (cy - sy) < 9 * 9) { best = e; break; }
      }
      if (best !== hover) { hover = best; pintar(); }
      if (best >= 0) { tip.textContent = "elemento " + (best + 1) + " · d = " + f.d[best].toFixed(3); tip.style.display = "block"; tip.style.left = Math.min(sx * r.width / W + 14, r.width - 170) + "px"; tip.style.top = (sy * r.height / H + 8) + "px"; }
      else tip.style.display = "none";
    };
    cv.onmouseleave = function () { hover = -1; tip.style.display = "none"; pintar(); };
    layout(); pintar();
    actual = { solo: solo, play: play, ir: ir };
    if (D.solo) setTimeout(function () { solo(true); }, 50);
    if (D.auto !== false) setTimeout(function () { if (!timer) play(); }, D.solo ? 700 : 400);
    root._hk = { ir: ir, play: play, solo: solo, frames: F };
  };
})();
