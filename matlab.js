window._c=window._c||function(l,d){return window.HK_DARK?d:l};
/* matlab.js — capa de ALTO NIVEL con nombres de MATLAB sobre el motor embebido (ML / glplot).
   Objetivo: escribir las graficas como en MATLAB (figure, plot, surf, contourf, bar, legend,
   title, xlabel, colorbar, axis equal ...) recibiendo VECTORES/MATRICES, sin tocar canvas ni JS crudo.
   No hay <script src>: este .js se EMBEBE inline junto a mlplot.js. Colormap = jet_r (siempre).

   Modelo: cada funcion acumula "ops" en la figura actual y programa un re-dibujo (flush) diferido,
   asi MATLAB calcula los limites de los ejes con TODOS los datos (auto-escala), como el de verdad. */
(function (global) {
  var ML = global.ML;
  var FIG = null, FIGN = 0;

  // ---- utilidades de arrays (acepta vector JS, o escalar) ----
  function isArr(a) { return Array.isArray(a); }
  function arr(a) { return isArr(a) ? a : [a]; }
  function isMat(a) { return isArr(a) && isArr(a[0]); }
  function rows(M) { return M.length; }
  function cols(M) { return M[0].length; }
  function minA(a) { var m = Infinity, i; for (i = 0; i < a.length; i++) if (a[i] < m) m = a[i]; return m; }
  function maxA(a) { var m = -Infinity, i; for (i = 0; i < a.length; i++) if (a[i] > m) m = a[i]; return m; }
  function minM(M) { var m = Infinity, i, j; for (i = 0; i < M.length; i++) for (j = 0; j < M[i].length; j++) if (M[i][j] < m) m = M[i][j]; return m; }
  function maxM(M) { var m = -Infinity, i, j; for (i = 0; i < M.length; i++) for (j = 0; j < M[i].length; j++) if (M[i][j] > m) m = M[i][j]; return m; }
  function range(n) { var a = [], i; for (i = 1; i <= n; i++) a.push(i); return a; }   // 1:n estilo MATLAB

  // paleta de Calcpad (chartPens): Tomato, YellowGreen, CornflowerBlue, oro, MediumVioletRed, ...
  var CORD = ["#FF6347", "#9ACD32", "#6495ED", "#F0D000", "#C71585", "#00FA9A", "#8A2BE2", "#FFA07A", "#FF1493", "#00CED1"];
  var CMAP = { r: "#e00000", g: "#00a000", b: "#0000ff", c: "#00bdbd", m: "#bd00bd", y: "#cccc00", k: "#000000", w: "#ffffff" };

  // parsea un "linespec" de MATLAB:  'r--o' , 'b:' , 'k.' , 'g-' ...
  function spec(s) {
    var o = { color: null, style: "-", marker: null };
    if (typeof s !== "string") return o;
    if (s.indexOf("--") >= 0) o.style = "--"; else if (s.indexOf("-.") >= 0) o.style = "-."; else if (s.indexOf(":") >= 0) o.style = ":"; else if (s.indexOf("-") >= 0) o.style = "-"; else o.style = "none";
    for (var i = 0; i < s.length; i++) { var ch = s[i]; if (CMAP[ch]) o.color = CMAP[ch]; if ("o.*+xsd^v><ph".indexOf(ch) >= 0) o.marker = ch; }
    return o;
  }

  // ---- figura ----
  function newFig() {
    var id = "mlfig" + (++FIGN);
    ML.figure(id, 600, 420);
    FIG = {
      id: id, ops: [], is3d: false,
      xmin: Infinity, xmax: -Infinity, ymin: Infinity, ymax: -Infinity, zmin: Infinity, zmax: -Infinity,
      ttl: null, xl: null, yl: null, zl: null, grid: true, equal: false, off: false,
      lim: null, az: -37.5, el: 30, cidx: 0, cbar: false, crange: null, legends: [], tip: null, sched: false
    };
    return FIG;
  }
  function fig() { return FIG || newFig(); }
  function nextColor() { var f = fig(); return CORD[(f.cidx++) % CORD.length]; }
  function bx(f, x, y, z) {
    if (x < f.xmin) f.xmin = x; if (x > f.xmax) f.xmax = x;
    if (y < f.ymin) f.ymin = y; if (y > f.ymax) f.ymax = y;
    if (z != null) { if (z < f.zmin) f.zmin = z; if (z > f.zmax) f.zmax = z; }
  }
  function sched(f) { if (f.sched) return; f.sched = true; setTimeout(function () { f.sched = false; flush2(f); }, 0); }   // el 3D (GL3) se dibuja directo, no por flush

  // ===================== 2D =====================
  function flush2(f) {
    var s = ML.figs[f.id], ctx = s.ctx; ML.cur = f.id;
    ctx.clearRect(0, 0, s.w, s.h);
    var dx0 = f.xmin, dx1 = f.xmax, dy0 = f.ymin, dy1 = f.ymax;     // rango de DATOS (esquinas)
    if (f.lim) { dx0 = f.lim[0]; dx1 = f.lim[1]; dy0 = f.lim[2]; dy1 = f.lim[3]; }
    if (!isFinite(dx0)) { dx0 = 0; dx1 = 1; dy0 = 0; dy1 = 1; }
    var x0 = dx0, x1 = dx1, y0 = dy0, y1 = dy1;
    var px = (x1 - x0) * 0.05 || 0.5, py = (y1 - y0) * 0.05 || 0.5;
    x0 -= px; x1 += px; y0 -= py; y1 += py;
    if (f.equal) ML.axis(x0, x1, y0, y1); else ML.axischart(x0, x1, y0, y1);
    if (f.cbar) { s.mR = 92; if (f.equal) { s.sc = Math.min((s.w - s.mL - s.mR) / (x1 - x0), (s.h - s.mT - s.mB) / (y1 - y0)); s.scx = s.sc; s.scy = s.sc; } else { s.scx = (s.w - s.mL - s.mR) / (x1 - x0); s.scy = (s.h - s.mT - s.mB) / (y1 - y0); } }
    s.dpts = []; s._tipBound = false; s.tipOn = false;
    // marco SOLO para charts de función o mapas; geometría (axis equal, sin grid) = dibujo limpio como Calcpad
    if (!f.off && (f.cbar || !f.equal || f.gridForced)) cpframe(f, s, ctx, x0, x1, y0, y1, dx0, dx1, dy0, dy1);
    var i;
    for (i = 0; i < f.ops.length; i++) drawOp(f, s, ctx, f.ops[i]);
    if (f.ttl) ML.title(f.ttl);
    if (f.cbar) { var cr = f.crange || [Math.min(y0, 0), y1]; ML._cbar(s, cr[0], cr[1]); }
    if (f.legends.length) drawLegend(f, s, ctx);
    if (s.dpts.length) ML.datatip(f.tip || "");        // cursor de datos (hover) por defecto
  }

  // ===== marco estilo Calcpad: grilla tenue, ejes negros en 0 con x/y, numeros en margenes, rangos en esquinas =====
  function niceStep(range, maxSteps) {
    var raw = range / Math.max(1, maxSteps); if (!(raw > 0)) return 1;
    var mag = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
  }
  function fmtN(v) {
    if (Math.abs(v) < 1e-12) return "0";
    var a = Math.abs(v);
    if (a >= 1e4 || a < 1e-3) return v.toExponential(1).replace("e+", "E").replace("e-", "E-").replace("e", "E");
    return parseFloat(v.toPrecision(4)).toString();
  }
  function hexA(hex, a) {
    var c = (hex || "#cc0000").replace("#", ""); if (c.length === 3) c = c[0] + c[0] + c[1] + c[1] + c[2] + c[2];
    return "rgba(" + parseInt(c.substr(0, 2), 16) + "," + parseInt(c.substr(2, 2), 16) + "," + parseInt(c.substr(4, 2), 16) + "," + a + ")";
  }
  function cpframe(f, s, ctx, x0, x1, y0, y1, dx0, dx1, dy0, dy1) {
    var L = s.mL, R = s.w - s.mR, T = s.mT, B = s.h - s.mB, v, p;
    ctx.font = "11px Segoe UI";
    var sy = niceStep(y1 - y0, 8);                 // grilla + numeros Y (margen izq, alineados der)
    ctx.textAlign = "right"; ctx.textBaseline = "middle";
    for (v = Math.ceil(y0 / sy) * sy; v <= y1 + 1e-9; v += sy) {
      p = ML.Y(v); ctx.strokeStyle = _c("rgba(0,0,0,0.08)","rgba(255,255,255,0.10)"); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(L, p); ctx.lineTo(R, p); ctx.stroke();
      ctx.fillStyle = _c("#777","#9a9180"); ctx.fillText(fmtN(v), L - 6, p);
    }
    var sx = niceStep(x1 - x0, 9);                 // grilla + numeros X (margen inf, centrados)
    ctx.textAlign = "center"; ctx.textBaseline = "top";
    for (v = Math.ceil(x0 / sx) * sx; v <= x1 + 1e-9; v += sx) {
      p = ML.X(v); ctx.strokeStyle = _c("rgba(0,0,0,0.08)","rgba(255,255,255,0.10)"); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(p, T); ctx.lineTo(p, B); ctx.stroke();
      ctx.fillStyle = _c("#777","#9a9180"); ctx.fillText(fmtN(v), p, B + 5);
    }
    ctx.strokeStyle = "rgba(0,0,0,0.25)"; ctx.lineWidth = 1; ctx.strokeRect(L, T, R - L, B - T);   // marco tenue
    ctx.lineWidth = 1.4; ctx.strokeStyle = _c("#000","#e8e2d4"); ctx.fillStyle = _c("#000","#e8e2d4");    // ejes NEGROS en 0 + x / y
    if (0 > y0 && 0 < y1) { p = ML.Y(0); ctx.beginPath(); ctx.moveTo(L, p); ctx.lineTo(R, p); ctx.stroke(); ctx.font = "italic 13px Georgia,serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle"; ctx.fillText(f.xl || "x", R + 6, p); }
    if (0 > x0 && 0 < x1) { p = ML.X(0); ctx.beginPath(); ctx.moveTo(p, T); ctx.lineTo(p, B); ctx.stroke(); ctx.font = "italic 13px Georgia,serif"; ctx.textAlign = "center"; ctx.textBaseline = "bottom"; ctx.fillText(f.yl || "y", p, T - 3); }
    ctx.fillStyle = _c("#555","#c9c0ad"); ctx.font = "11px Segoe UI"; ctx.textBaseline = "alphabetic";   // rangos en esquinas
    ctx.textAlign = "left"; ctx.fillText("[" + fmtN(dx0) + "; " + fmtN(dy0) + "]", 3, s.h - 3);
    ctx.textAlign = "right"; ctx.fillText("[" + fmtN(dx1) + "; " + fmtN(dy1) + "]", s.w - 3, T - 4);
  }

  function dash(ctx, style) {
    if (style === "--") ctx.setLineDash([7, 5]); else if (style === ":") ctx.setLineDash([2, 4]);
    else if (style === "-.") ctx.setLineDash([8, 4, 2, 4]); else ctx.setLineDash([]);
  }

  function drawOp(f, s, ctx, op) {
    var i, X = ML.X.bind(ML), Y = ML.Y.bind(ML);
    if (op.t === "line") {
      if (op.fill) {                                  // relleno tenue hasta y=0 (estilo Calcpad)
        var st = ML.S(), b0 = Math.min(Math.max(0, st.ymin), st.ymax), yb = Y(b0);
        ctx.beginPath(); ctx.moveTo(X(op.x[0]), yb);
        for (i = 0; i < op.x.length; i++) ctx.lineTo(X(op.x[i]), Y(op.y[i]));
        ctx.lineTo(X(op.x[op.x.length - 1]), yb); ctx.closePath();
        ctx.fillStyle = hexA(op.color, 0.10); ctx.fill();
      }
      if (op.style !== "none") {
        ctx.strokeStyle = op.color; ctx.lineWidth = op.lw || 2.2; dash(ctx, op.style);
        ctx.beginPath(); ctx.moveTo(X(op.x[0]), Y(op.y[0]));
        for (i = 1; i < op.x.length; i++) ctx.lineTo(X(op.x[i]), Y(op.y[i]));
        ctx.stroke(); ctx.setLineDash([]);
      }
      if (op.marker) for (i = 0; i < op.x.length; i++) ML.marker(op.x[i], op.y[i], op.marker, op.color);
      for (i = 0; i < op.x.length; i++) ML.datapoint(op.x[i], op.y[i], op.y[i]);
    } else if (op.t === "patch") {                      // cuadrilátero/polígono coloreado jet (como Calcpad)
      var pp = []; for (i = 0; i < op.x.length; i++) pp.push(op.x[i], op.y[i]); ML.patch(pp, op.tv);
    } else if (op.t === "cline") {                      // elemento 1D con GRADIENTE de color continuo por valor (jet_r)
      var dc = (op.cmax - op.cmin) || 1;
      for (i = 0; i < op.x.length - 1; i++) {
        var ax = X(op.x[i]), ay = Y(op.y[i]), bx2 = X(op.x[i + 1]), by2 = Y(op.y[i + 1]);
        var g = ctx.createLinearGradient(ax, ay, bx2, by2);
        g.addColorStop(0, ML.jet((op.c[i] - op.cmin) / dc)); g.addColorStop(1, ML.jet((op.c[i + 1] - op.cmin) / dc));
        ctx.strokeStyle = g; ctx.lineWidth = op.lw || 3; ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx2, by2); ctx.stroke();
      }
      for (i = 0; i < op.x.length; i++) ML.datapoint(op.x[i], op.y[i], op.c[i]);
    } else if (op.t === "scatter") {
      for (i = 0; i < op.x.length; i++) { ML.marker(op.x[i], op.y[i], op.mk || "o", op.color); ML.datapoint(op.x[i], op.y[i], op.y[i]); }
    } else if (op.t === "bar") {
      for (i = 0; i < op.x.length; i++) ML.bar(op.x[i], op.y[i], op.w, op.color);
    } else if (op.t === "stem") {
      for (i = 0; i < op.x.length; i++) ML.stem(op.x[i], op.y[i], op.color);
    } else if (op.t === "area") {
      for (i = 0; i < op.x.length - 1; i++) ML.area(op.x[i], op.y[i], op.x[i + 1], op.y[i + 1], op.color);
    } else if (op.t === "stairs") {
      for (i = 0; i < op.x.length - 1; i++) ML.stairs(op.x[i], op.y[i], op.x[i + 1], op.y[i + 1], op.color);
    } else if (op.t === "errorbar") {
      ctx.strokeStyle = op.color; ctx.lineWidth = 1.6; ctx.beginPath(); ctx.moveTo(X(op.x[0]), Y(op.y[0])); for (i = 1; i < op.x.length; i++) ctx.lineTo(X(op.x[i]), Y(op.y[i])); ctx.stroke();
      for (i = 0; i < op.x.length; i++) ML.errorbar(op.x[i], op.y[i], op.e[i], op.color);
    } else if (op.t === "fill") {
      var p = []; for (i = 0; i < op.x.length; i++) p.push(op.x[i], op.y[i]); ML.fill(p, op.color);
    } else if (op.t === "quiver") {
      for (i = 0; i < op.x.length; i++) ML.quiver(op.x[i], op.y[i], op.u[i] * op.sc, op.v[i] * op.sc, op.color);
    } else if (op.t === "imagesc" || op.t === "pcolor" || op.t === "contourf") {
      var Z = op.Z, nr = rows(Z), nc = cols(Z), zmin = minM(Z), zmax = maxM(Z), dz = (zmax - zmin) || 1;
      var gx = op.x, gy = op.y, r, c2;
      for (r = 0; r < nr; r++) for (c2 = 0; c2 < nc; c2++) {
        var xc = gx[c2], yc = gy[r], w = (c2 < nc - 1 ? gx[c2 + 1] - gx[c2] : gx[c2] - gx[c2 - 1]), h = (r < nr - 1 ? gy[r + 1] - gy[r] : gy[r] - gy[r - 1]);
        ML.imagesc(xc, yc, w, h, (Z[r][c2] - zmin) / dz);
      }
      if (op.t === "contourf" || op.t === "contour") drawContourLines(f, s, op);
    } else if (op.t === "contour") {
      drawContourLines(f, s, op);
    } else if (op.t === "pie") {
      var tot = 0; for (i = 0; i < op.v.length; i++) tot += op.v[i]; var a = 90;
      for (i = 0; i < op.v.length; i++) { var sweep = op.v[i] / tot * 360, a2 = a - sweep; ML.pie(0, 0, 1, a, a2, CORD[i % CORD.length]); var am = (a + a2) / 2 * 0.0174533; ML.text(1.15 * Math.cos(am), 1.15 * Math.sin(am), (100 * op.v[i] / tot).toFixed(1) + "%", _c("#222","#f3eddd")); a = a2; }
    } else if (op.t === "polar") {
      ctx.strokeStyle = op.color; ctx.lineWidth = 1.8; ctx.beginPath();
      for (i = 0; i < op.th.length; i++) { var aa = op.th[i] * 0.0174533, xx = op.r[i] * Math.cos(aa), yy = op.r[i] * Math.sin(aa); if (i === 0) ctx.moveTo(X(xx), Y(yy)); else ctx.lineTo(X(xx), Y(yy)); } ctx.stroke();
    } else if (op.t === "text") {
      ML.text(op.x, op.y, op.s, op.color);
    }
  }

  function drawContourLines(f, s, op) {
    var Z = op.Z, nr = rows(Z), nc = cols(Z), zmin = minM(Z), zmax = maxM(Z), nl = op.nl || 8, L, r, c2;
    for (L = 1; L < nl; L++) {
      var lv = zmin + L / nl * (zmax - zmin);
      for (r = 0; r < nr - 1; r++) for (c2 = 0; c2 < nc - 1; c2++)
        ML.contourCell(op.x[c2], op.y[r], op.x[c2 + 1], op.y[r + 1], Z[r][c2], Z[r][c2 + 1], Z[r + 1][c2 + 1], Z[r + 1][c2], lv, _c("#222","#f3eddd"));
    }
  }

  function drawLegend(f, s, ctx) {
    var n = f.legends.length, bw = 120, bh = 16 * n + 8, x = s.w - s.mR - bw - 8, y = s.mT + 6, i;
    ctx.fillStyle = _c("rgba(255,255,255,0.85)","rgba(26,23,18,0.85)"); ctx.strokeStyle = "#999"; ctx.lineWidth = 1;
    ctx.fillRect(x, y, bw, bh); ctx.strokeRect(x, y, bw, bh);
    ctx.font = "11px Segoe UI"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    for (i = 0; i < n; i++) {
      var yy = y + 12 + i * 16; ctx.strokeStyle = f.legends[i].color; ctx.lineWidth = 2.2;
      ctx.beginPath(); ctx.moveTo(x + 8, yy); ctx.lineTo(x + 28, yy); ctx.stroke();
      ctx.fillStyle = _c("#222","#f3eddd"); ctx.fillText(f.legends[i].label, x + 34, yy);
    }
  }

  // ===================== 3D (usa el pipeline 3D interactivo de ML) =====================
  function flush3(f) {
    var s = ML.figs[f.id]; ML.cur = f.id;
    ML.view3(f.az, f.el);
    ML.axis3(f.xmin, f.xmax, f.ymin, f.ymax, f.zmin, f.zmax);
    var i; for (i = 0; i < f.ops.length; i++) build3(f, f.ops[i]);
    // datapoints para el hover 3D (cursor que muestra x,y,z del nudo mas cercano)
    for (i = 0; i < f.ops.length; i++) {
      var op = f.ops[i];
      if (op.t === "surf" || op.t === "mesh") { for (var a = 0; a < rows(op.Z); a++) for (var b = 0; b < cols(op.Z); b++) ML.datapoint3(op.X[a][b], op.Y[a][b], op.Z[a][b], op.Z[a][b]); }
      else if (op.t === "plot3" || op.t === "scatter3") { for (var k = 0; k < op.x.length; k++) ML.datapoint3(op.x[k], op.y[k], op.z[k], op.z[k]); }
    }
    if (f.cbar) ML.colorbar((f.crange || [f.zmin, f.zmax])[0], (f.crange || [f.zmin, f.zmax])[1]);
    ML.render3();
  }
  function build3(f, op) {
    var i, j, dz = (f.zmax - f.zmin) || 1;
    if (op.t === "surf" || op.t === "mesh") {
      var X = op.X, Y = op.Y, Z = op.Z, nr = rows(Z), nc = cols(Z);
      for (i = 0; i < nr - 1; i++) for (j = 0; j < nc - 1; j++) {
        var p = [X[i][j], Y[i][j], Z[i][j], X[i][j + 1], Y[i][j + 1], Z[i][j + 1], X[i + 1][j + 1], Y[i + 1][j + 1], Z[i + 1][j + 1], X[i + 1][j], Y[i + 1][j], Z[i + 1][j]];
        var zm = (Z[i][j] + Z[i][j + 1] + Z[i + 1][j + 1] + Z[i + 1][j]) / 4;
        if (op.t === "surf") ML.fill3(p, (zm - f.zmin) / dz);
        else { var c = ML.jet((zm - f.zmin) / dz); ML.line3(p[0], p[1], p[2], p[3], p[4], p[5], c); ML.line3(p[3], p[4], p[5], p[6], p[7], p[8], c); ML.line3(p[6], p[7], p[8], p[9], p[10], p[11], c); ML.line3(p[9], p[10], p[11], p[0], p[1], p[2], c); }
      }
    } else if (op.t === "plot3") {
      for (i = 0; i < op.x.length - 1; i++) ML.line3(op.x[i], op.y[i], op.z[i], op.x[i + 1], op.y[i + 1], op.z[i + 1], op.color);
    } else if (op.t === "scatter3") {
      for (i = 0; i < op.x.length; i++) ML.line3(op.x[i], op.y[i], op.z[i], op.x[i], op.y[i], op.z[i], op.color);
    } else if (op.t === "text3") {
      ML.text3(op.x, op.y, op.z, op.s, op.color);
    }
  }

  // ===================== API GLOBAL con nombres de MATLAB =====================
  function figure() { return newFig(); }
  function clf() { var f = fig(); f.ops = []; f.legends = []; f.cidx = 0; f.xmin = Infinity; f.xmax = -Infinity; f.ymin = Infinity; f.ymax = -Infinity; f.zmin = Infinity; f.zmax = -Infinity; sched(f); }
  function hold() { }   // en este modelo las series siempre se acumulan en la figura actual

  function plot(x, y, sp) {            // plot(y) | plot(x,y) | plot(x,y,'r--o')
    var f = fig(); if (y === undefined || typeof y === "string") { sp = y; y = arr(x); x = range(y.length); } else { x = arr(x); y = arr(y); }
    var o = spec(sp); var col = o.color || nextColor();
    for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]);
    f.ops.push({ t: "line", x: x, y: y, color: col, style: o.style, marker: o.marker, fill: true, lw: 2.4 }); sched(f); return f;
  }
  function scatter(x, y, sz, c) { var f = fig(); x = arr(x); y = arr(y); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.ops.push({ t: "scatter", x: x, y: y, color: (typeof c === "string" ? c : nextColor()), mk: "o" }); sched(f); }
  function line(x, y, sp) { var f = fig(); x = arr(x); y = arr(y); var o = spec(sp); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.ops.push({ t: "line", x: x, y: y, color: o.color || _c("#333","#e8e2d4"), style: o.style === "none" ? "-" : o.style, marker: o.marker, fill: false, lw: 1.8 }); sched(f); }
  function cline(x, y, c) { var f = fig(); x = arr(x); y = arr(y); c = arr(c); var cmin = minA(c), cmax = maxA(c); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.crange = [cmin, cmax]; f.cbar = true; f.tip = f.tip || "valor"; f.ops.push({ t: "cline", x: x, y: y, c: c, cmin: cmin, cmax: cmax, lw: 3 }); sched(f); }
  function cline3(x, y, z, c) {
    var f = fig(); x = arr(x); y = arr(y); z = arr(z); c = arr(c); var cmin = minA(c), cmax = maxA(c), dc = (cmax - cmin) || 1, i;
    gl3init(f); GL3.axis3(minA(x), maxA(x), minA(y), maxA(y), minA(z), maxA(z));
    GL3.cartesian3(minA(x), maxA(x), minA(y), maxA(y), minA(z), maxA(z), 6, 6);
    for (i = 0; i < x.length - 1; i++) GL3.line3(x[i], y[i], z[i], x[i + 1], y[i + 1], z[i + 1], jethex(((c[i] + c[i + 1]) / 2 - cmin) / dc));
    for (i = 0; i < x.length; i++) GL3.datapoint(x[i], y[i], z[i], c[i]);
    GL3.datatip("valor"); GL3.colorbar3(cmin, cmax, 360); GL3.render3();
  }
  function patch(x, y, t) { var f = fig(); x = arr(x); y = arr(y); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.ops.push({ t: "patch", x: x, y: y, tv: (t == null ? 0.5 : t) }); sched(f); }
  function bar(x, y, c) { var f = fig(); if (y === undefined) { y = arr(x); x = range(y.length); } else { x = arr(x); y = arr(y); } var w = (x.length > 1 ? (x[1] - x[0]) * 0.7 : 0.7); for (var i = 0; i < x.length; i++) bx(f, x[i] - w, y[i]), bx(f, x[i] + w, 0); f.ops.push({ t: "bar", x: x, y: y, w: w, color: (c || CORD[0]) }); sched(f); }
  function stem(x, y, c) { var f = fig(); if (y === undefined) { y = arr(x); x = range(y.length); } else { x = arr(x); y = arr(y); } for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]), bx(f, x[i], 0); f.ops.push({ t: "stem", x: x, y: y, color: (c || CORD[0]) }); sched(f); }
  function area(x, y, c) { var f = fig(); x = arr(x); y = arr(y); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]), bx(f, x[i], 0); f.ops.push({ t: "area", x: x, y: y, color: c }); sched(f); }
  function stairs(x, y, c) { var f = fig(); x = arr(x); y = arr(y); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.ops.push({ t: "stairs", x: x, y: y, color: (c || _c("#333","#e8e2d4")) }); sched(f); }
  function errorbar(x, y, e, c) { var f = fig(); x = arr(x); y = arr(y); e = arr(e); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i] - e[i]), bx(f, x[i], y[i] + e[i]); f.ops.push({ t: "errorbar", x: x, y: y, e: e, color: (c || _c("#333","#e8e2d4")) }); sched(f); }
  function fill(x, y, c) { var f = fig(); x = arr(x); y = arr(y); for (var i = 0; i < x.length; i++) bx(f, x[i], y[i]); f.ops.push({ t: "fill", x: x, y: y, color: (typeof c === "string" && CMAP[c] ? CMAP[c] : (c || CORD[0])) }); sched(f); }
  function quiver(x, y, u, v, c) { var f = fig(); x = arr(x); y = arr(y); u = arr(u); v = arr(v); var mx = 0; for (var i = 0; i < u.length; i++) mx = Math.max(mx, Math.hypot(u[i], v[i])); var spc = (x.length > 1 ? Math.abs(x[1] - x[0]) || 1 : 1); var scl = mx > 0 ? spc / mx : 1; for (i = 0; i < x.length; i++) { bx(f, x[i], y[i]); bx(f, x[i] + u[i] * scl, y[i] + v[i] * scl); } f.ops.push({ t: "quiver", x: x, y: y, u: u, v: v, sc: scl, color: (c || CORD[0]) }); sched(f); }
  function histogram(d, nb) { d = arr(d); nb = nb || Math.ceil(Math.sqrt(d.length)); var lo = minA(d), hi = maxA(d), w = (hi - lo) / nb || 1, cnt = [], cx = [], i; for (i = 0; i < nb; i++) { cnt[i] = 0; cx[i] = lo + (i + 0.5) * w; } for (i = 0; i < d.length; i++) { var k = Math.min(nb - 1, Math.floor((d[i] - lo) / w)); cnt[k]++; } var f = fig(); for (i = 0; i < nb; i++) bx(f, cx[i] - w / 2, cnt[i]), bx(f, cx[i] + w / 2, 0); f.ops.push({ t: "bar", x: cx, y: cnt, w: w * 0.95, color: CORD[0] }); sched(f); }
  function pie(v) { var f = fig(); v = arr(v); f.equal = true; f.off = true; f.xmin = -1.4; f.xmax = 1.4; f.ymin = -1.4; f.ymax = 1.4; f.ops.push({ t: "pie", v: v }); sched(f); }
  function polarplot(th, r, c) { var f = fig(); th = arr(th); r = arr(r); f.equal = true; var rm = maxA(r.map(Math.abs)); bx(f, -rm, -rm); bx(f, rm, rm); f.ops.push({ t: "polar", th: th, r: r, color: (spec(c).color || nextColor()) }); sched(f); }
  function imagesc(a, b, C) { var f = fig(); var Z = (C === undefined ? a : C); var gx, gy; if (C === undefined) { gx = range(cols(Z)); gy = range(rows(Z)); } else { gx = arr(a); gy = arr(b); } for (var i = 0; i < gx.length; i++) bx(f, gx[i], gy[0]); bx(f, gx[gx.length - 1], gy[gy.length - 1]); f.equal = true; f.crange = [minM(Z), maxM(Z)]; f.cbar = true; f.ops.push({ t: "imagesc", x: gx, y: gy, Z: Z }); sched(f); }
  function pcolor(a, b, C) { imagesc(a, b, C); fig().ops[fig().ops.length - 1].t = "pcolor"; }
  function contourf(a, b, C, n) { gridplot("contourf", a, b, C, n); }
  function contour(a, b, C, n) { gridplot("contour", a, b, C, n); }
  function gridplot(kind, a, b, C, n) { var f = fig(); var Z, gx, gy; if (C === undefined || typeof C === "number") { Z = a; n = b; gx = range(cols(Z)); gy = range(rows(Z)); } else { gx = isMat(a) ? a[0] : arr(a); gy = isMat(b) ? b.map(function (r) { return r[0]; }) : arr(b); Z = C; } for (var i = 0; i < gx.length; i++) bx(f, gx[i], gy[0]); bx(f, gx[gx.length - 1], gy[gy.length - 1]); f.crange = [minM(Z), maxM(Z)]; f.cbar = true; f.ops.push({ t: kind, x: gx, y: gy, Z: Z, nl: n || 10 }); sched(f); }

  // ---- 3D ----
  // ===== 3D con GL3 (glplot.js, WebGL suave) — igual que Calcpad-FEM-3D =====
  function hex6(c) { return (c || "#cc0000").replace("#", ""); }
  function jethex(t) { var c = GL3.jet(t); function h2(n) { n = Math.round(n * 255); return (n < 16 ? "0" : "") + n.toString(16); } return h2(c[0]) + h2(c[1]) + h2(c[2]); }
  function gl3init(f) {                                  // quita el canvas ML vacío y crea el lienzo WebGL en su lugar
    var m = ML.figs[f.id]; if (m && m.cv && m.cv.parentNode && m.cv.parentNode.parentNode) m.cv.parentNode.parentNode.removeChild(m.cv.parentNode);
    GL3.figure3("gl_" + f.id, 600, 440); GL3.view3(f.az, f.el);
  }
  function surf(X, Y, Z) { surf3("surf", X, Y, Z); }
  function mesh(X, Y, Z) { surf3("mesh", X, Y, Z); }
  function surf3(kind, X, Y, Z) {
    var f = fig();
    if (Z === undefined) { Z = X; X = []; Y = []; for (var r = 0; r < rows(Z); r++) { X[r] = []; Y[r] = []; for (var c = 0; c < cols(Z); c++) { X[r][c] = c + 1; Y[r][c] = r + 1; } } }
    var nr = rows(Z), nc = cols(Z), i, j, xmn = Infinity, xmx = -Infinity, ymn = Infinity, ymx = -Infinity, zmn = Infinity, zmx = -Infinity;
    for (i = 0; i < nr; i++) for (j = 0; j < nc; j++) { var x = X[i][j], y = Y[i][j], z = Z[i][j]; if (x < xmn) xmn = x; if (x > xmx) xmx = x; if (y < ymn) ymn = y; if (y > ymx) ymx = y; if (z < zmn) zmn = z; if (z > zmx) zmx = z; }
    var dz = (zmx - zmn) || 1;
    gl3init(f);
    GL3.axis3(xmn, xmx, ymn, ymx, zmn, zmx);
    GL3.cartesian3(xmn, xmx, ymn, ymx, zmn, zmx, Math.min(8, nc - 1) || 1, Math.min(8, nr - 1) || 1);   // plano cartesiano XYZ
    for (i = 0; i < nr - 1; i++) for (j = 0; j < nc - 1; j++) {
      var t1 = (Z[i][j] - zmn) / dz, t2 = (Z[i][j + 1] - zmn) / dz, t3 = (Z[i + 1][j + 1] - zmn) / dz, t4 = (Z[i + 1][j] - zmn) / dz;
      if (kind === "surf") GL3.fill3([X[i][j], Y[i][j], Z[i][j], X[i][j + 1], Y[i][j + 1], Z[i][j + 1], X[i + 1][j + 1], Y[i + 1][j + 1], Z[i + 1][j + 1], X[i + 1][j], Y[i + 1][j], Z[i + 1][j]], t1, t2, t3, t4);
      else { var col = jethex((t1 + t3) / 2); GL3.line3(X[i][j], Y[i][j], Z[i][j], X[i][j + 1], Y[i][j + 1], Z[i][j + 1], col); GL3.line3(X[i][j], Y[i][j], Z[i][j], X[i + 1][j], Y[i + 1][j], Z[i + 1][j], col); }
    }
    for (i = 0; i < nr; i++) for (j = 0; j < nc; j++) GL3.datapoint(X[i][j], Y[i][j], Z[i][j], Z[i][j]);
    GL3.datatip("z"); GL3.colorbar3(zmn, zmx, 360); GL3.render3();
  }
  function plot3(x, y, z, sp) {
    var f = fig(); x = arr(x); y = arr(y); z = arr(z);
    gl3init(f); GL3.axis3(minA(x), maxA(x), minA(y), maxA(y), minA(z), maxA(z));
    GL3.cartesian3(minA(x), maxA(x), minA(y), maxA(y), minA(z), maxA(z), 6, 6);
    var col = hex6(spec(sp).color || nextColor()), i;
    for (i = 0; i < x.length - 1; i++) GL3.line3(x[i], y[i], z[i], x[i + 1], y[i + 1], z[i + 1], col);
    for (i = 0; i < x.length; i++) GL3.datapoint(x[i], y[i], z[i], z[i]);
    GL3.datatip("z"); GL3.render3();
  }
  function scatter3(x, y, z, c) {
    var f = fig(); x = arr(x); y = arr(y); z = arr(z);
    var zmn = minA(z), zmx = maxA(z), dz = (zmx - zmn) || 1, i;
    gl3init(f); GL3.axis3(minA(x), maxA(x), minA(y), maxA(y), zmn, zmx);
    GL3.cartesian3(minA(x), maxA(x), minA(y), maxA(y), zmn, zmx, 6, 6);
    for (i = 0; i < x.length; i++) { GL3.point3(x[i], y[i], z[i], (z[i] - zmn) / dz); GL3.datapoint(x[i], y[i], z[i], z[i]); }
    GL3.datatip("z"); GL3.colorbar3(zmn, zmx, 360); GL3.render3();
  }

  // ---- decoradores / ejes ----
  function title(s) { var f = fig(); f.ttl = s; sched(f); }
  function xlabel(s) { var f = fig(); f.xl = s; sched(f); }
  function ylabel(s) { var f = fig(); f.yl = s; sched(f); }
  function zlabel(s) { var f = fig(); f.zl = s; sched(f); }
  function legend() { var f = fig(), a = arguments, k = 0, i; for (i = 0; i < f.ops.length && k < a.length; i++) { var op = f.ops[i]; if (op.color && (op.t === "line" || op.t === "scatter")) f.legends.push({ label: a[k++], color: op.color }); } sched(f); }
  function colorbar() { var f = fig(); f.cbar = true; sched(f); }
  function caxis(lo, hi) { var f = fig(); f.crange = [lo, hi]; sched(f); }
  function colormap() { }   // siempre jet_r (lo fija el motor)
  function grid(s) { var f = fig(); f.gridForced = (s !== "off" && s !== false); sched(f); }
  function view(az, el) { var f = fig(); f.az = az; f.el = el; sched(f); }
  function text(x, y, s, c) { var f = fig(); if (f.is3d) { f.ops.push({ t: "text3", x: x, y: y, z: arguments[2], s: arguments[3], color: arguments[4] || _c("#222","#f3eddd") }); } else { bx(f, x, y); f.ops.push({ t: "text", x: x, y: y, s: s, color: c || _c("#222","#f3eddd") }); } sched(f); }
  function datacursor(label) { var f = fig(); f.tip = label || "y"; sched(f); }
  function axis(a, b, c, d) {
    var f = fig();
    if (a === "equal") f.equal = true;
    else if (a === "normal" || a === "auto") f.equal = false;
    else if (a === "off") f.off = true;
    else if (a === "on") f.off = false;
    else if (isArr(a)) f.lim = a;
    else if (b !== undefined) f.lim = [a, b, c, d];
    sched(f);
  }
  function semilogy(x, y, sp) { plot(x, y, sp); }   // (ejes log: se aproximan como lineales en este motor)
  function semilogx(x, y, sp) { plot(x, y, sp); }
  function loglog(x, y, sp) { plot(x, y, sp); }
  function subplot() { return figure(); }            // simplificado: cada subplot = nueva figura

  // helpers de datos util (estilo MATLAB), por si el reporte los necesita
  function linspace(a, b, n) { n = n || 100; var o = [], i; for (i = 0; i < n; i++) o.push(a + (b - a) * i / (n - 1)); return o; }
  function meshgrid(x, y) { y = y || x; var X = [], Y = [], i, j; for (i = 0; i < y.length; i++) { X[i] = []; Y[i] = []; for (j = 0; j < x.length; j++) { X[i][j] = x[j]; Y[i][j] = y[i]; } } return [X, Y]; }
  function zeros(r, c) { c = c || r; var M = [], i, j; for (i = 0; i < r; i++) { M[i] = []; for (j = 0; j < c; j++) M[i][j] = 0; } return M; }

  // exporta TODOS los nombres MATLAB al ambito global
  var api = {
    figure: figure, clf: clf, hold: hold, plot: plot, line: line, cline: cline, cline3: cline3, patch: patch, scatter: scatter, bar: bar, stem: stem, area: area,
    stairs: stairs, errorbar: errorbar, fill: fill, quiver: quiver, histogram: histogram, hist: histogram,
    pie: pie, polarplot: polarplot, polar: polarplot, imagesc: imagesc, pcolor: pcolor, contourf: contourf,
    contour: contour, surf: surf, mesh: mesh, surfc: surf, plot3: plot3, scatter3: scatter3,
    title: title, xlabel: xlabel, ylabel: ylabel, zlabel: zlabel, legend: legend, colorbar: colorbar,
    caxis: caxis, colormap: colormap, grid: grid, view: view, text: text, axis: axis,
    semilogy: semilogy, semilogx: semilogx, loglog: loglog, subplot: subplot, datacursor: datacursor,
    linspace: linspace, meshgrid: meshgrid, zeros: zeros
  };
  for (var k in api) global[k] = api[k];
  global.MLAB = api;
})(window);
