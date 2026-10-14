// Hekatan OpenSees — ventana de dibujo 2D/3D estilo Hekatan LISP (planta, frente, lateral, iso, órbita, OSNAP, línea de órdenes).
// Dibuja barras, áreas y sólidos del modelo y lo que se dibuje con el cursor (línea, cara, círculo, caja).
// Cada entidad nueva se escribe en el guion como una línea  `# linea x y z x y z`  dentro de #dibujar … #enddibujar
// (comentarios para OpenSees: el mismo .tcl corre en el OpenSees oficial). Guarda en DXF y DWG como Hekatan LISP.
(function () {
  "use strict";
  var HK = window.HKCAD = {};
  var ACI = { BARRAS: 1, AREAS: 5, SOLIDOS: 3, NUDOS: 2, APOYOS: 30, DIBUJO: 7, "0": 7 };
  var COL = { BARRAS: ["#c62828", "#ff6b5e"], AREAS: ["#1c5fbf", "#6aa6ff"], SOLIDOS: ["#2b8a3e", "#6fd6a0"], NUDOS: ["#7a1fa8", "#c9a7f0"],
              APOYOS: ["#d9480f", "#ff9a5e"], DIBUJO: ["#171310", "#e8e2d4"] };
  var dark = function () { return !!window.HK_DARK; };
  function colorCapa(c) { var p = COL[c] || COL.DIBUJO; return p[dark() ? 1 : 0]; }
  function fx(v) { return Math.abs(v) < 1e-12 ? "0" : String(+(+v).toFixed(6)); }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function len(a) { return Math.sqrt(dot(a, a)); }
  function P3(p) { return [+p[0] || 0, +p[1] || 0, +p[2] || 0]; }

  function post(msg) {
    try { if (window.chrome && chrome.webview) chrome.webview.postMessage(JSON.stringify(msg)); } catch (e) { }
  }

  // ---------- DXF R12 y JSON de acadrust (el mismo que usa Hekatan LISP) ----------
  function capasDe(ents) { var s = {}; ents.forEach(function (e) { s[e.c || "DIBUJO"] = 1; }); return Object.keys(s); }
  HK.aDxf = function (ents) {
    var o = ["0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", String(capasDe(ents).length)];
    capasDe(ents).forEach(function (n) { o.push("0", "LAYER", "2", n, "70", "0", "62", String(ACI[n] || 7), "6", "CONTINUOUS"); });
    o.push("0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES");
    var pt = function (g, p) { return [String(g), fx(p[0]), String(g + 10), fx(p[1]), String(g + 20), fx(p[2])]; };
    ents.forEach(function (e) {
      var cap = e.c || "DIBUJO";
      if (e.t === "L") o.push.apply(o, ["0", "LINE", "8", cap].concat(pt(10, e.a), pt(11, e.b)));
      else if (e.t === "F") { var p = e.p; o.push.apply(o, ["0", "3DFACE", "8", cap].concat(pt(10, p[0]), pt(11, p[1]), pt(12, p[2]), pt(13, p[3] || p[2]))); }
      else if (e.t === "C") o.push.apply(o, ["0", "CIRCLE", "8", cap].concat(pt(10, e.p), ["40", fx(e.r)]));
      else if (e.t === "T") o.push.apply(o, ["0", "TEXT", "8", cap].concat(pt(10, e.p), ["40", fx(e.h || 0.2), "1", e.s || ""]));
    });
    o.push("0", "ENDSEC", "0", "EOF");
    return o.join("\r\n") + "\r\n";
  };
  HK.aDwgJson = function (ents) {
    var P = function (p) { return [+fx(p[0]), +fx(p[1]), +fx(p[2])]; };
    var out = [];
    ents.forEach(function (e) {
      var com = [[0, ""], [8, e.c || "DIBUJO"]], t;
      if (e.t === "L") { com[0][1] = "LINE"; out.push(com.concat([[10, P(e.a)], [11, P(e.b)]])); }
      else if (e.t === "F") { com[0][1] = "3DFACE"; t = e.p; out.push(com.concat([[10, P(t[0])], [11, P(t[1])], [12, P(t[2])], [13, P(t[3] || t[2])]])); }
      else if (e.t === "C") { com[0][1] = "CIRCLE"; out.push(com.concat([[10, P(e.p)], [40, e.r]])); }
      else if (e.t === "T") { com[0][1] = "TEXT"; out.push(com.concat([[10, P(e.p)], [40, e.h || 0.2], [1, e.s || ""]])); }
    });
    return JSON.stringify({ version: "AC1032", layers: capasDe(ents).map(function (n) { return { name: n, color: ACI[n] || 7 }; }), entities: out });
  };

  // ---------- DIBUJO -> MODELO OpenSees: nudos, barras (lineas) y cascaras (caras de 4 puntos) de la capa DIBUJO ----------
  HK.aOpenSees = function (ents) {
    var nodos = [], idx = {}, tag0 = 1001, out = [];
    function nodo(p) {
      var k = fx(p[0]) + "," + fx(p[1]) + "," + fx(p[2]);
      if (idx[k] == null) { idx[k] = tag0 + nodos.length; nodos.push(p); }
      return idx[k];
    }
    var lin = ents.filter(function (e) { return e.t === "L" && (e.c || "DIBUJO") === "DIBUJO"; });
    var car = ents.filter(function (e) { return e.t === "F" && (e.c || "DIBUJO") === "DIBUJO" && e.p.length >= 4 && e.p[3] !== e.p[2]; });
    if (!lin.length && !car.length) return "";
    var el = [], e0 = 1001;
    lin.forEach(function (e, i) {
      var a = nodo(e.a), b = nodo(e.b), d = sub(e.b, e.a), vert = Math.abs(d[2]) > 0.999 * len(d);
      el.push("element elasticBeamColumn " + (e0 + i) + " " + a + " " + b + " $A $Ew $Gw $J $Iy $Iz " + (vert ? 9002 : 9001));
    });
    var sh = [];
    car.forEach(function (e, i) { sh.push("element ShellMITC4 " + (e0 + lin.length + i) + " " + e.p.slice(0, 4).map(nodo).join(" ") + " 9001"); });
    out.push("## Modelo generado desde el dibujo");
    out.push("# Nudos y elementos de la capa DIBUJO. **Edita** las propiedades de abajo (E, A, I, espesor) y añade los apoyos (`fix`) y las cargas.");
    out.push("wipe", "model basic -ndm 3 -ndf 6");
    out.push("set Ew 2.5e7; set Gw 1.04e7; set A 0.09; set J 1.4e-3; set Iy 6.75e-4; set Iz 6.75e-4");
    nodos.forEach(function (p, i) { out.push("node " + (tag0 + i) + " " + fx(p[0]) + " " + fx(p[1]) + " " + fx(p[2])); });
    out.push("geomTransf Linear 9001 0 0 1", "geomTransf Linear 9002 1 0 0");
    if (sh.length) out.push("section ElasticMembranePlateSection 9001 $Ew 0.2 0.15 2.4");
    return out.concat(el, sh).join("\n") + "\n";
  };

  // ---------- ventana ----------
  HK.mount = function (id, data) {
    var root = document.getElementById(id);
    if (!root) return;
    var ents = (data.ents || []).slice(), W = data.w || 760, H = data.h || 470;
    root.className = "hkcad";
    root.innerHTML =
      '<div class="hkcad-bar"></div>' +
      '<canvas width="' + W + '" height="' + H + '"></canvas>' +
      '<div class="hkcad-tip"></div>' +
      '<div class="hkcad-cmd"><span class="hkcad-pr">Orden:</span><input type="text" spellcheck="false" placeholder="LINEA · CARA · CIRCULO · x,y,z · @dx,dy,dz · PLANTA · ISO · BORRAR"/></div>' +
      '<div class="hkcad-st"></div>';
    var bar = root.querySelector(".hkcad-bar"), cv = root.querySelector("canvas"), ctx = cv.getContext("2d"),
        tip = root.querySelector(".hkcad-tip"), inp = root.querySelector("input"), st = root.querySelector(".hkcad-st");
    var S = { yaw: -2.356, pitch: 0.615, zoom: 1, pan: [0, 0], tool: null, pts: [], ortho: false, snap: true, osnap: true, grid: data.grid || 0.5,
              plane: "z", zw: 0, mouse: null, hover: -1, added: [], vista: "Iso SO" };
    var T = [0, 0, 0], sc = 1;                           // objetivo y escala (px por unidad)

    // ----- cámara ortográfica -----
    function basis() {
      var cy = Math.cos(S.yaw), sy = Math.sin(S.yaw), cp = Math.cos(S.pitch), sp = Math.sin(S.pitch);
      return { r: [-sy, cy, 0], u: [-sp * cy, -sp * sy, cp], f: [-cp * cy, -cp * sy, -sp] };
    }
    function pts(e) { return e.t === "L" ? [e.a, e.b] : e.t === "F" ? e.p : [e.p]; }
    function bounds() {
      var mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30], n = 0;
      ents.forEach(function (e) { var ps = pts(e); if (e.t === "C") ps = [[e.p[0] - e.r, e.p[1] - e.r, e.p[2]], [e.p[0] + e.r, e.p[1] + e.r, e.p[2]]];
        ps.forEach(function (p) { n++; for (var k = 0; k < 3; k++) { if (p[k] < mn[k]) mn[k] = p[k]; if (p[k] > mx[k]) mx[k] = p[k]; } }); });
      if (!n) { mn = [0, 0, 0]; mx = [10, 10, 5]; }
      return { mn: mn, mx: mx };
    }
    function ajustar() {
      var b = bounds(); T = [(b.mn[0] + b.mx[0]) / 2, (b.mn[1] + b.mx[1]) / 2, (b.mn[2] + b.mx[2]) / 2];
      var B = basis(), xs = [1e30, -1e30], ys = [1e30, -1e30];
      [b.mn[0], b.mx[0]].forEach(function (x) { [b.mn[1], b.mx[1]].forEach(function (y) { [b.mn[2], b.mx[2]].forEach(function (z) {
        var d = sub([x, y, z], T), a = dot(d, B.r), c = dot(d, B.u); xs = [Math.min(xs[0], a), Math.max(xs[1], a)]; ys = [Math.min(ys[0], c), Math.max(ys[1], c)]; }); }); });
      sc = 0.86 * Math.min(W / Math.max(xs[1] - xs[0], 1e-6), H / Math.max(ys[1] - ys[0], 1e-6)); S.zoom = 1; S.pan = [0, 0];
    }
    function proj(p) {
      var B = basis(), d = sub(p, T), s = sc * S.zoom;
      return [W / 2 + S.pan[0] + dot(d, B.r) * s, H / 2 + S.pan[1] - dot(d, B.u) * s, dot(d, B.f)];
    }
    function planoVista() {
      var f = basis().f;
      if (Math.abs(f[2]) > 0.2) return "z";
      return Math.abs(f[1]) > Math.abs(f[0]) ? "y" : "x";
    }
    function screenToPlane(sx, sy) {
      var B = basis(), s = sc * S.zoom, a = (sx - W / 2 - S.pan[0]) / s, c = -(sy - H / 2 - S.pan[1]) / s, pl = planoVista();
      var k = pl === "z" ? 2 : pl === "y" ? 1 : 0, w0 = pl === "z" ? S.zw : 0;
      var base = [T[0] + B.r[0] * a + B.u[0] * c, T[1] + B.r[1] * a + B.u[1] * c, T[2] + B.r[2] * a + B.u[2] * c];
      var t = (w0 - base[k]) / (B.f[k] || 1e-9);
      return [base[0] + B.f[0] * t, base[1] + B.f[1] * t, base[2] + B.f[2] * t];
    }
    function snapGrid(p) { var g = S.grid; return g > 0 ? p.map(function (v) { return Math.round(v / g) * g; }) : p; }
    function vertices() {
      var v = [];
      ents.forEach(function (e, i) {
        if (e.t === "L") { v.push([e.a, "extremo", i], [e.b, "extremo", i], [[(e.a[0] + e.b[0]) / 2, (e.a[1] + e.b[1]) / 2, (e.a[2] + e.b[2]) / 2], "medio", i]); }
        else if (e.t === "F") e.p.forEach(function (q) { v.push([q, "extremo", i]); });
        else if (e.t === "C") v.push([e.p, "centro", i]);
      });
      return v;
    }
    // ----- OSNAP: extremo, medio, centro, INTERSECCION, PERPENDICULAR (como el CAD de Hekatan LISP) -----
    function segDist(px, py, a, b) { return dist2seg(px, py, a, b); }
    function lineasCerca(sx, sy, rad) {
      var r = [];
      ents.forEach(function (e, i) {
        if (e.t === "L") { var A = proj(e.a), B = proj(e.b); if (segDist(sx, sy, A, B) < rad) r.push(e); }
        else if (e.t === "F") { for (var k = 0; k < e.p.length; k++) { var a2 = e.p[k], b2 = e.p[(k + 1) % e.p.length];
          if (segDist(sx, sy, proj(a2), proj(b2)) < rad) r.push({ t: "L", a: a2, b: b2 }); } }
      });
      return r.slice(0, 40);
    }
    function interseccion(l1, l2) {              // dos segmentos que de verdad se cortan en 3D
      var d1 = sub(l1.b, l1.a), d2 = sub(l2.b, l2.a), w0 = sub(l1.a, l2.a), a = dot(d1, d1), b = dot(d1, d2), c = dot(d2, d2),
          d = dot(d1, w0), e = dot(d2, w0), den = a * c - b * b;
      if (den < 1e-12 * a * c) return null;      // paralelas
      var t = (b * e - c * d) / den, u = (a * e - b * d) / den;
      if (t < -1e-9 || t > 1 + 1e-9 || u < -1e-9 || u > 1 + 1e-9) return null;
      var q1 = [l1.a[0] + t * d1[0], l1.a[1] + t * d1[1], l1.a[2] + t * d1[2]], q2 = [l2.a[0] + u * d2[0], l2.a[1] + u * d2[1], l2.a[2] + u * d2[2]];
      var tol = 1e-6 * Math.max(Math.sqrt(a), Math.sqrt(c), 1e-9);
      return len(sub(q1, q2)) < Math.max(tol, 1e-7) ? q1 : null;
    }
    function pickPoint(sx, sy) {
      var cand = [], V = vertices(), i, j;                                  // [punto, tipo, ventaja en px^2]
      if (S.osnap) {
        for (i = 0; i < V.length; i++) cand.push([V[i][0], V[i][1], V[i][1] === "extremo" || V[i][1] === "centro" ? 24 : 10]);
        var L = lineasCerca(sx, sy, 40);
        for (i = 0; i < L.length; i++) for (j = i + 1; j < L.length; j++) { var q = interseccion(L[i], L[j]); if (q) cand.push([q, "intersección", 18]); }
        if (S.tool && S.pts.length) {                                        // PERPENDICULAR desde el ultimo punto
          var o = S.pts[S.pts.length - 1];
          for (i = 0; i < L.length; i++) {
            var d = sub(L[i].b, L[i].a), dd = dot(d, d); if (dd < 1e-18) continue;
            var t = dot(sub(o, L[i].a), d) / dd; if (t < 0.001 || t > 0.999) continue;
            cand.push([[L[i].a[0] + t * d[0], L[i].a[1] + t * d[1], L[i].a[2] + t * d[2]], "perpendicular", 6]);
          }
        }
      }
      var best = null, bd = 1e30;
      for (i = 0; i < cand.length; i++) {
        var qq = proj(cand[i][0]), dx = qq[0] - sx, dy = qq[1] - sy, d2 = dx * dx + dy * dy;
        if (d2 > 100) continue;                                             // radio de captura: 10 px
        var score = d2 - cand[i][2];
        if (score < bd) { bd = score; best = cand[i]; }
      }
      if (best) return { p: best[0].slice(), snap: best[1] };
      var p = screenToPlane(sx, sy); if (S.snap) p = snapGrid(p);
      var pl = planoVista(); if (pl === "z") p[2] = S.zw;
      if (S.ortho && S.pts.length) { var l = S.pts[S.pts.length - 1], dx2 = Math.abs(p[0] - l[0]), dy2 = Math.abs(p[1] - l[1]), dz2 = Math.abs(p[2] - l[2]);
        if (dx2 >= dy2 && dx2 >= dz2) { p[1] = l[1]; p[2] = l[2]; } else if (dy2 >= dz2) { p[0] = l[0]; p[2] = l[2]; } else { p[0] = l[0]; p[1] = l[1]; } }
      return { p: p, snap: null };
    }

    // ----- dibujo -----
    function cara(e) { var p = e.p, n = cross(sub(p[1], p[0]), sub(p[2], p[0])); return 0.5 * len(n) + (p[3] ? 0.5 * len(cross(sub(p[2], p[0]), sub(p[3], p[0]))) : 0); }
    function dist2seg(px, py, a, b) { var dx = b[0] - a[0], dy = b[1] - a[1], l2 = dx * dx + dy * dy, t = l2 ? Math.max(0, Math.min(1, ((px - a[0]) * dx + (py - a[1]) * dy) / l2)) : 0;
      var x = a[0] + t * dx, y = a[1] + t * dy; return Math.sqrt((px - x) * (px - x) + (py - y) * (py - y)); }
    function marcador(q, tipo) {                 // forma del marcador de OSNAP, como AutoCAD
      ctx.strokeStyle = "#e0a000"; ctx.lineWidth = 1.8; var x = q[0], y = q[1];
      ctx.beginPath();
      if (tipo === "extremo") ctx.rect(x - 6, y - 6, 12, 12);
      else if (tipo === "medio") { ctx.moveTo(x, y - 7); ctx.lineTo(x + 7, y + 6); ctx.lineTo(x - 7, y + 6); ctx.closePath(); }
      else if (tipo === "centro") ctx.arc(x, y, 6, 0, 6.2832);
      else if (tipo === "intersección") { ctx.moveTo(x - 6, y - 6); ctx.lineTo(x + 6, y + 6); ctx.moveTo(x + 6, y - 6); ctx.lineTo(x - 6, y + 6); }
      else { ctx.moveTo(x - 7, y - 7); ctx.lineTo(x - 7, y + 5); ctx.lineTo(x + 5, y + 5); ctx.moveTo(x - 7, y); ctx.lineTo(x - 2, y); ctx.lineTo(x - 2, y + 5); }
      ctx.stroke();
    }
    function pintar() {
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = dark() ? "#1a1712" : "#FFFDF6"; ctx.fillRect(0, 0, W, H);
      // rejilla del plano de trabajo (solo planta)
      if (planoVista() === "z" && S.grid > 0 && S.grid * sc * S.zoom > 7) {
        var b = bounds(), g = S.grid, x0 = Math.floor(b.mn[0] / g) * g - 2 * g, x1 = b.mx[0] + 2 * g, y0 = Math.floor(b.mn[1] / g) * g - 2 * g, y1 = b.mx[1] + 2 * g;
        ctx.strokeStyle = dark() ? "rgba(255,255,255,.07)" : "rgba(0,0,0,.07)"; ctx.lineWidth = 1; ctx.beginPath();
        for (var x = x0; x <= x1; x += g) { var A = proj([x, y0, S.zw]), B2 = proj([x, y1, S.zw]); ctx.moveTo(A[0], A[1]); ctx.lineTo(B2[0], B2[1]); }
        for (var y = y0; y <= y1; y += g) { var C = proj([x0, y, S.zw]), D = proj([x1, y, S.zw]); ctx.moveTo(C[0], C[1]); ctx.lineTo(D[0], D[1]); }
        ctx.stroke();
      }
      // caras al fondo (ordenadas por profundidad), luego líneas
      var fs = [];
      ents.forEach(function (e, i) { if (e.t === "F") { var q = e.p.map(proj); fs.push([q, i, q.reduce(function (s, v) { return s + v[2]; }, 0) / q.length]); } });
      fs.sort(function (a, b) { return b[2] - a[2]; });
      fs.forEach(function (f) {
        var c = colorCapa(ents[f[1]].c); ctx.beginPath(); f[0].forEach(function (q, k) { if (k) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); }); ctx.closePath();
        ctx.fillStyle = c; ctx.globalAlpha = f[1] === S.hover ? 0.45 : 0.22; ctx.fill(); ctx.globalAlpha = 1; ctx.strokeStyle = c; ctx.lineWidth = 1; ctx.stroke();
      });
      ents.forEach(function (e, i) {
        var c = colorCapa(e.c); ctx.strokeStyle = i === S.hover ? (dark() ? "#fff" : "#000") : c; ctx.fillStyle = c; ctx.lineWidth = i === S.hover ? 2.4 : 1.5;
        if (e.t === "L") { var a = proj(e.a), b = proj(e.b); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
        else if (e.t === "C") { ctx.beginPath(); for (var k = 0; k <= 48; k++) { var t = k / 48 * 6.2832, q = proj([e.p[0] + e.r * Math.cos(t), e.p[1] + e.r * Math.sin(t), e.p[2]]); if (k) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); } ctx.stroke(); }
        else if (e.t === "T") { var q2 = proj(e.p); ctx.font = Math.max(10, (e.h || 0.2) * sc * S.zoom) + "px Segoe UI"; ctx.fillText(e.s || "", q2[0], q2[1]); }
      });
      // apoyos y nudos
      // goma elástica de lo que se está dibujando
      if (S.tool && S.pts.length && S.mouse) {
        var m = S.mouse.p, last = S.pts[S.pts.length - 1];
        ctx.strokeStyle = "#e000d0"; ctx.lineWidth = 1.2; ctx.setLineDash([5, 4]); ctx.beginPath();
        S.pts.forEach(function (p, k) { var q = proj(p); if (k) ctx.lineTo(q[0], q[1]); else ctx.moveTo(q[0], q[1]); });
        var qm = proj(m); ctx.lineTo(qm[0], qm[1]); if (S.tool === "cara" && S.pts.length >= 2) { var q0 = proj(S.pts[0]); ctx.lineTo(q0[0], q0[1]); }
        ctx.stroke(); ctx.setLineDash([]);
        if (S.tool === "circulo") { var r = len(sub(m, S.pts[0])); ctx.beginPath(); for (var k2 = 0; k2 <= 48; k2++) { var t2 = k2 / 48 * 6.2832, q3 = proj([S.pts[0][0] + r * Math.cos(t2), S.pts[0][1] + r * Math.sin(t2), S.pts[0][2]]); if (k2) ctx.lineTo(q3[0], q3[1]); else ctx.moveTo(q3[0], q3[1]); } ctx.stroke(); }
      }
      // cursor y marcador de OSNAP
      if (S.mouse) {
        var mq = proj(S.mouse.p); ctx.strokeStyle = S.mouse.snap ? "#e0a000" : (dark() ? "#e8e2d4" : "#171310"); ctx.lineWidth = 1.4;
        if (S.mouse.snap) { marcador(mq, S.mouse.snap); ctx.fillStyle = "#e0a000"; ctx.font = "11px Segoe UI"; ctx.fillText(S.mouse.snap, mq[0] + 12, mq[1] - 10); }
        else { ctx.beginPath(); ctx.moveTo(mq[0] - 7, mq[1]); ctx.lineTo(mq[0] + 7, mq[1]); ctx.moveTo(mq[0], mq[1] - 7); ctx.lineTo(mq[0], mq[1] + 7); ctx.stroke(); }
      }
      // triada y vista
      var B = basis(), ox = 36, oy = H - 30; ctx.font = "11px Segoe UI"; ctx.lineWidth = 1.6;
      [["X", [1, 0, 0], "#c62828"], ["Y", [0, 1, 0], "#2b8a3e"], ["Z", [0, 0, 1], "#1c5fbf"]].forEach(function (a) {
        var x = dot(a[1], B.r) * 24, y = -dot(a[1], B.u) * 24; ctx.strokeStyle = a[2]; ctx.fillStyle = a[2]; ctx.beginPath(); ctx.moveTo(ox, oy); ctx.lineTo(ox + x, oy + y); ctx.stroke(); ctx.fillText(a[0], ox + x * 1.2 - 3, oy + y * 1.2 + 4); });
      st.textContent = S.vista + " · Plano " + planoVista().toUpperCase() + (planoVista() === "z" ? " (z = " + fx(S.zw) + ")" : "") + " · " + ents.length + " entidades" +
        (S.mouse ? " · x = " + fx(S.mouse.p[0]) + "  y = " + fx(S.mouse.p[1]) + "  z = " + fx(S.mouse.p[2]) : "") + (S.ortho ? " · ORTO" : "") + (S.osnap ? " · OSNAP" : "") + (S.snap ? " · REJILLA " + S.grid : "") + (S.tool ? " · " + S.tool.toUpperCase() : "");
    }
    function vista(n) {
      var v = { Planta: [-1.5708, 1.5708], Frente: [-1.5708, 0], Lateral: [0, 0], "Iso SO": [-2.356, 0.615], "Iso SE": [-0.785, 0.615] }[n]; if (!v) return;
      S.yaw = v[0]; S.pitch = v[1]; S.vista = n; ajustar(); pintar();
    }

    // ----- creación de entidades (y aviso al guion) -----
    function agregar(e, linea) { ents.push(e); S.added.push(linea); post({ tipo: "dibujo-add", linea: linea }); pintar(); }
    function pt3(p) { return fx(p[0]) + " " + fx(p[1]) + " " + fx(p[2]); }
    function nuevaLinea(a, b) { agregar({ t: "L", a: a.slice(), b: b.slice(), c: "DIBUJO" }, "linea " + pt3(a) + "  " + pt3(b)); }
    function nuevaCara(p) { agregar({ t: "F", p: p.map(function (q) { return q.slice(); }), c: "DIBUJO" }, "cara " + p.map(pt3).join("  ")); }
    function nuevoCirculo(c, r) { agregar({ t: "C", p: c.slice(), r: r, c: "DIBUJO" }, "circulo " + pt3(c) + "  " + fx(r)); }
    function punto(p) {
      if (!S.tool) return;
      if (S.tool === "linea") { if (S.pts.length) { nuevaLinea(S.pts[S.pts.length - 1], p); S.pts = [p]; } else S.pts = [p]; }
      else if (S.tool === "cara") { S.pts.push(p); if (S.pts.length === 4) { nuevaCara(S.pts); S.pts = []; } }
      else if (S.tool === "circulo") { if (!S.pts.length) S.pts = [p]; else { var r = len(sub(p, S.pts[0])); if (r > 1e-9) nuevoCirculo(S.pts[0], r); S.pts = []; } }
      pintar();
    }
    function terminar() { if (S.tool === "cara" && S.pts.length === 3) nuevaCara(S.pts); S.pts = []; pintar(); }
    function deshacer() { if (!S.added.length) return; ents.pop(); S.added.pop(); post({ tipo: "dibujo-undo" }); pintar(); }
    function herramienta(t) { S.tool = t; S.pts = []; Array.prototype.forEach.call(bar.querySelectorAll("button[data-t]"), function (b) { b.classList.toggle("on", b.getAttribute("data-t") === t); }); pintar(); }
    function guardar(fmt) {
      var nombre = (data.nombre || "dibujo");
      post({ tipo: "dibujo-guardar", fmt: fmt, nombre: nombre, dxf: fmt === "dxf" ? HK.aDxf(ents) : null, json: fmt === "dwg" ? HK.aDwgJson(ents) : null });
    }

    // ----- barra de botones -----
    [["Planta", function () { vista("Planta"); }], ["Frente", function () { vista("Frente"); }], ["Lateral", function () { vista("Lateral"); }], ["Iso", function () { vista("Iso SO"); }],
     ["|", null], ["Línea", function () { herramienta("linea"); }, "linea"], ["Cara", function () { herramienta("cara"); }, "cara"], ["Círculo", function () { herramienta("circulo"); }, "circulo"],
     ["Cursor", function () { herramienta(null); }, ""], ["Borrar", deshacer], ["|", null],
     ["Orto", function () { S.ortho = !S.ortho; pintar(); }], ["OSNAP", function () { S.osnap = !S.osnap; pintar(); }], ["Rejilla", function () { S.snap = !S.snap; pintar(); }], ["Encuadre", function () { ajustar(); pintar(); }], ["|", null],
     ["A OpenSees", function () { var t = HK.aOpenSees(ents); if (t) post({ tipo: "dibujo-modelo", tcl: t }); else st.textContent = "Nada que convertir: dibuja líneas o caras de 4 puntos en la capa DIBUJO"; }], ["Guardar DXF", function () { guardar("dxf"); }], ["Guardar DWG", function () { guardar("dwg"); }]].forEach(function (b) {
      if (b[0] === "|") { var sp = document.createElement("span"); sp.className = "hkcad-sep"; bar.appendChild(sp); return; }
      var btn = document.createElement("button"); btn.textContent = b[0]; if (b[2] != null) btn.setAttribute("data-t", b[2]); btn.onclick = b[1]; bar.appendChild(btn);
    });

    // ----- ratón -----
    var drag = null;
    cv.addEventListener("contextmenu", function (e) { e.preventDefault(); if (S.tool) terminar(); });
    cv.addEventListener("mousedown", function (e) {
      var r = cv.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width, sy = (e.clientY - r.top) * H / r.height;
      if (e.button === 1 || (e.button === 0 && e.shiftKey)) { drag = { m: e.button === 1 && !e.shiftKey ? "orbita" : "pan", x: e.clientX, y: e.clientY }; e.preventDefault(); return; }
      if (e.button === 0) {
        if (S.tool) { punto(pickPoint(sx, sy).p); }
        else drag = { m: "orbita", x: e.clientX, y: e.clientY };
      }
    });
    window.addEventListener("mouseup", function () { drag = null; });
    window.addEventListener("mousemove", function (e) {
      if (!drag) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (drag.m === "orbita") { S.yaw -= dx * 0.008; S.pitch = Math.max(-1.5708, Math.min(1.5708, S.pitch + dy * 0.008)); S.vista = "Órbita"; }
      else { S.pan[0] += dx; S.pan[1] += dy; }
      pintar();
    });
    cv.addEventListener("mousemove", function (e) {
      var r = cv.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width, sy = (e.clientY - r.top) * H / r.height;
      if (!drag) { S.mouse = pickPoint(sx, sy); }
      // entidad bajo el cursor (datatip estilo Hekatan Lab)
      var best = -1, bd = 7;
      ents.forEach(function (en, i) {
        var d = 1e9;
        if (en.t === "L") { var a = proj(en.a), b = proj(en.b); d = dist2seg(sx, sy, a, b); }
        else if (en.t === "F") { var q = en.p.map(proj); for (var k = 0; k < q.length; k++) d = Math.min(d, dist2seg(sx, sy, q[k], q[(k + 1) % q.length])); }
        else if (en.t === "C") { var c = proj(en.p); d = Math.abs(Math.sqrt((sx - c[0]) * (sx - c[0]) + (sy - c[1]) * (sy - c[1])) - en.r * sc * S.zoom); }
        if (d < bd) { bd = d; best = i; }
      });
      S.hover = S.tool ? -1 : best;
      if (S.hover >= 0) {
        var en = ents[S.hover], txt = (en.c || "DIBUJO") + (en.t === "L" ? " · L = " + fx(len(sub(en.b, en.a))) + " m" : en.t === "F" ? " · A = " + fx(cara(en)) + " m²" : en.t === "C" ? " · r = " + fx(en.r) : "");
        tip.textContent = txt; tip.style.display = "block"; tip.style.left = Math.min(sx + 14, W - 160) + "px"; tip.style.top = (sy + 36) + "px";
      } else tip.style.display = "none";
      pintar();
    });
    cv.addEventListener("wheel", function (e) {
      e.preventDefault(); var r = cv.getBoundingClientRect(), sx = (e.clientX - r.left) * W / r.width, sy = (e.clientY - r.top) * H / r.height, k = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      S.pan[0] = sx - W / 2 - (sx - W / 2 - S.pan[0]) * k; S.pan[1] = sy - H / 2 - (sy - H / 2 - S.pan[1]) * k; S.zoom *= k; pintar();
    }, { passive: false });
    root.addEventListener("keydown", function (e) { if (e.key === "Escape") { S.pts = []; herramienta(null); } if (e.key === "z" && e.ctrlKey) deshacer(); });

    // ----- línea de órdenes: x,y,z · @dx,dy,dz · palabras -----
    inp.addEventListener("keydown", function (e) {
      if (e.key !== "Enter") { e.stopPropagation(); return; }
      var s = inp.value.trim(); inp.value = ""; if (!s) { terminar(); return; }
      var u = s.toUpperCase(), tools = { L: "linea", LINEA: "linea", LINE: "linea", C: "circulo", CIRCULO: "circulo", CIRCLE: "circulo", F: "cara", CARA: "cara", "3DCARA": "cara" };
      if (tools[u]) { herramienta(tools[u]); return; }
      if (u === "BORRAR" || u === "U" || u === "UNDO") { deshacer(); return; }
      if (u === "PLANTA" || u === "TOP") { vista("Planta"); return; } if (u === "FRENTE" || u === "FRONT") { vista("Frente"); return; }
      if (u === "LATERAL" || u === "RIGHT") { vista("Lateral"); return; } if (u === "ISO") { vista("Iso SO"); return; }
      if (u === "ZOOM" || u === "ENCUADRE" || u === "TODO") { ajustar(); pintar(); return; } if (u === "ORTO") { S.ortho = !S.ortho; pintar(); return; } if (u === "OSNAP") { S.osnap = !S.osnap; pintar(); return; }
      var rel = s[0] === "@", nums = s.replace("@", "").split(/[ ,;]+/).map(Number);
      if (nums.length >= 2 && nums.every(function (v) { return isFinite(v); })) {
        var p = P3(nums), base = S.pts.length ? S.pts[S.pts.length - 1] : [0, 0, 0];
        if (rel) p = [base[0] + p[0], base[1] + p[1], base[2] + p[2]]; else if (nums.length === 2) p[2] = S.zw;
        if (!S.tool) herramienta("linea"); punto(p);
      }
    });
    cv.tabIndex = 0;
    ajustar(); vista(data.vista || "Iso SO");
    root._hk = { ents: ents, vista: vista, guardar: guardar, pick: pickPoint, proj: proj, S: S };
  };
})();
