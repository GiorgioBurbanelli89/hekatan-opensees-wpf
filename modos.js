// Hekatan OpenSees — modos de vibración ANIMADOS de una estructura 3D (barras y áreas), orbitable con el ratón.
// Los vectores propios los calcula OpenSees (eigen) y los imprime el guion como  HKMODO k T | ux uy uz ...  (un modo por línea).
// Controles: modo 1..n, Reproducir/Pausa, amplitud, vistas, estructura sin deformar, «Solo animación» (F11; Esc sale).
(function () {
  "use strict";
  var HM = window.HKMODOS = {};
  var actual = null;
  function jet(t) {
    t = Math.max(0, Math.min(1, t));
    var r = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 3))), g = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 2))), b = Math.min(1, Math.max(0, 1.5 - Math.abs(4 * t - 1)));
    return "rgb(" + Math.round(255 * r) + "," + Math.round(255 * g) + "," + Math.round(255 * b) + ")";
  }
  HM.solo = function (on) { if (actual) actual.solo(on); };
  HM.mount = function (id, D) {
    var root = document.getElementById(id); if (!root) return;
    var W0 = D.w || 760, H0 = D.h || 470, W = W0, H = H0, N = D.nodes, BAR = D.bars, QUAD = D.quads, MOD = D.modes;
    root.className = "hkgr hkmod";
    var botones = MOD.map(function (m, i) { return '<button class="m" data-k="' + i + '" title="T = ' + m.T.toFixed(4) + ' s">Modo ' + m.k + '</button>'; }).join("");
    root.innerHTML = '<div class="hkgr-bar mb">' + botones + '</div><canvas width="' + W + '" height="' + H + '"></canvas>' +
      '<div class="hkgr-bar"><button class="pl">⏸ Pausa</button><label>amplitud <input class="amp" type="range" min="0" max="3" step="0.05" value="1"/></label>' +
      '<button class="v" data-v="iso">Iso</button><button class="v" data-v="planta">Planta</button><button class="v" data-v="frente">Frente</button><button class="v" data-v="lateral">Lateral</button>' +
      '<label><input class="gh" type="checkbox" checked/> sin deformar</label>' +
      '<button class="so" title="Solo la animación a pantalla completa (F11; Esc para salir)">⛶ Solo animación</button></div><div class="hkgr-st"></div>';
    var cv = root.querySelector("canvas"), ctx = cv.getContext("2d"), pl = root.querySelector(".pl"), amp = root.querySelector(".amp"), st = root.querySelector(".hkgr-st"),
        so = root.querySelector(".so"), gh = root.querySelector(".gh");
    var S = { yaw: -2.356, pitch: 0.55, zoom: 1, pan: [0, 0], modo: 0, t0: Date.now(), play: true, solo: false, fase: null };
    var mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30];
    N.forEach(function (p) { for (var k = 0; k < 3; k++) { if (p[k] < mn[k]) mn[k] = p[k]; if (p[k] > mx[k]) mx[k] = p[k]; } });
    var C = [(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2], size = Math.max(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) || 1;
    var sc = 1, nodo = N.length;
    function basis() { var cy = Math.cos(S.yaw), sy = Math.sin(S.yaw), cp = Math.cos(S.pitch), sp = Math.sin(S.pitch); return { r: [-sy, cy, 0], u: [-sp * cy, -sp * sy, cp] }; }
    function fit() {
      var B = basis(), a = [1e30, -1e30], b = [1e30, -1e30];
      N.forEach(function (p) { var d = [p[0] - C[0], p[1] - C[1], p[2] - C[2]], x = d[0] * B.r[0] + d[1] * B.r[1] + d[2] * B.r[2], y = d[0] * B.u[0] + d[1] * B.u[1] + d[2] * B.u[2];
        a = [Math.min(a[0], x), Math.max(a[1], x)]; b = [Math.min(b[0], y), Math.max(b[1], y)]; });
      sc = 0.78 * Math.min((W - 90) / Math.max(a[1] - a[0], 1e-9), (H - 60) / Math.max(b[1] - b[0], 1e-9)); S.zoom = 1; S.pan = [-20, 0];
    }
    function proj(p) { var B = basis(), d = [p[0] - C[0], p[1] - C[1], p[2] - C[2]], s = sc * S.zoom; return [W / 2 + S.pan[0] + (d[0] * B.r[0] + d[1] * B.r[1] + d[2] * B.r[2]) * s, H / 2 + S.pan[1] - (d[0] * B.u[0] + d[1] * B.u[1] + d[2] * B.u[2]) * s]; }
    function dark() { return !!window.HK_DARK; }
    function pos(i, f) { var m = MOD[S.modo].u, A = f * (+amp.value) * 0.10 * size; return [N[i][0] + A * m[3 * i], N[i][1] + A * m[3 * i + 1], N[i][2] + A * m[3 * i + 2]]; }
    function mag(i) { var m = MOD[S.modo].u; return Math.sqrt(m[3 * i] * m[3 * i] + m[3 * i + 1] * m[3 * i + 1] + m[3 * i + 2] * m[3 * i + 2]) / 1.7320508; }
    function pintar() {
      var T = MOD[S.modo].T, per = Math.min(2.5, Math.max(1.2, T * 6));                     // un ciclo de animacion mas lento que el real, legible
      var f = S.fase != null ? S.fase : Math.sin(2 * Math.PI * ((Date.now() - S.t0) / 1000) / per);
      var bg = dark() ? "#1a1712" : "#FFFDF6", fg = dark() ? "#e8e2d4" : "#171310", fs = Math.max(11, Math.round(W / 70));
      ctx.fillStyle = bg; ctx.fillRect(0, 0, W, H);
      var P = N.map(function (p, i) { return proj(pos(i, f)); }), P0 = gh.checked ? N.map(function (p) { return proj(p); }) : null;
      if (P0) {
        ctx.strokeStyle = dark() ? "rgba(255,255,255,.18)" : "rgba(0,0,0,.18)"; ctx.lineWidth = 0.6; ctx.beginPath();
        BAR.forEach(function (b) { ctx.moveTo(P0[b[0]][0], P0[b[0]][1]); ctx.lineTo(P0[b[1]][0], P0[b[1]][1]); }); ctx.stroke();
      }
      var Z = function (i) { var B = basis(); var p = pos(i, f), d = [p[0] - C[0], p[1] - C[1], p[2] - C[2]]; return -(d[0] * Math.cos(S.pitch) * Math.cos(S.yaw) + d[1] * Math.cos(S.pitch) * Math.sin(S.yaw) + d[2] * Math.sin(S.pitch)); };
      QUAD.forEach(function (q) {
        var tm = (mag(q[0]) + mag(q[1]) + mag(q[2]) + mag(q[3])) / 4;
        ctx.beginPath(); q.forEach(function (i, k) { if (k) ctx.lineTo(P[i][0], P[i][1]); else ctx.moveTo(P[i][0], P[i][1]); }); ctx.closePath();
        ctx.globalAlpha = 0.55; ctx.fillStyle = jet(tm); ctx.fill(); ctx.globalAlpha = 1;
      });
      ctx.lineWidth = Math.max(1, W / 700);
      BAR.forEach(function (b) { ctx.strokeStyle = jet((mag(b[0]) + mag(b[1])) / 2); ctx.beginPath(); ctx.moveTo(P[b[0]][0], P[b[0]][1]); ctx.lineTo(P[b[1]][0], P[b[1]][1]); ctx.stroke(); });
      var bw = Math.max(14, W / 50), bx = W - 60 - bw, by = 30, bh = H - 70;
      for (var i = 0; i < 40; i++) { ctx.fillStyle = jet(1 - i / 39); ctx.fillRect(bx, by + i * bh / 40, bw, bh / 40 + 1); }
      ctx.strokeStyle = fg; ctx.lineWidth = 1; ctx.strokeRect(bx, by, bw, bh); ctx.fillStyle = fg; ctx.font = fs + "px Segoe UI"; ctx.textBaseline = "middle"; ctx.textAlign = "left";
      [0, 0.5, 1].forEach(function (t) { ctx.fillText(t.toFixed(1), bx + bw + 5, by + bh * (1 - t)); });
      var txt = "Modo " + MOD[S.modo].k + " · T = " + T.toFixed(4) + " s · f = " + (1 / T).toFixed(3) + " Hz";
      st.textContent = txt + " · amplitud ×" + (+amp.value).toFixed(2);
      ctx.font = "bold " + Math.round(fs * 1.4) + "px Segoe UI"; ctx.fillStyle = fg; ctx.fillText(txt, 14, 20);
    }
    function loop() { if (S.play || S.fase != null) pintar(); requestAnimationFrame(loop); }
    function vista(n) { var v = { iso: [-2.356, 0.55], planta: [-1.5708, 1.5708], frente: [-1.5708, 0], lateral: [0, 0] }[n]; S.yaw = v[0]; S.pitch = v[1]; fit(); pintar(); }
    function modo(k) { S.modo = Math.max(0, Math.min(MOD.length - 1, k)); S.t0 = Date.now(); Array.prototype.forEach.call(root.querySelectorAll("button.m"), function (b) { b.classList.toggle("on", +b.getAttribute("data-k") === S.modo); }); pintar(); }
    function ajustar() { var barras = root.querySelectorAll(".hkgr-bar"), h = 0; Array.prototype.forEach.call(barras, function (b) { h += b.getBoundingClientRect().height; });
      W = Math.max(400, window.innerWidth); H = Math.max(300, window.innerHeight - h - 30); cv.width = W; cv.height = H; fit(); pintar(); }
    function solo(on) {
      if (on === undefined) on = !S.solo; if (on === S.solo) return; S.solo = on;
      document.documentElement.classList.toggle("hkgr-solo", on); so.textContent = on ? "✕ Salir (Esc)" : "⛶ Solo animación";
      if (on) { ajustar(); window.addEventListener("resize", ajustar); } else { window.removeEventListener("resize", ajustar); W = W0; H = H0; cv.width = W; cv.height = H; fit(); pintar(); }
    }
    root.querySelectorAll("button.m").forEach(function (b) { b.onclick = function () { modo(+b.getAttribute("data-k")); }; });
    root.querySelectorAll("button.v").forEach(function (b) { b.onclick = function () { vista(b.getAttribute("data-v")); }; });
    pl.onclick = function () { S.play = !S.play; pl.textContent = S.play ? "⏸ Pausa" : "▶ Reproducir"; S.t0 = Date.now(); };
    so.onclick = function () { solo(); }; gh.onchange = pintar; amp.oninput = pintar;
    window.addEventListener("keydown", function (e) { if (e.key === "F11") { e.preventDefault(); solo(); } else if (e.key === "Escape" && S.solo) solo(false);
      else if (S.solo && e.key >= "1" && e.key <= "9") modo(+e.key - 1); else if (S.solo && e.key === " ") { e.preventDefault(); pl.onclick(); } });
    // órbita con el ratón: izquierdo = girar, Mayús = mover, rueda = zoom
    var drag = null;
    cv.onmousedown = function (e) { drag = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 1 }; e.preventDefault(); };
    window.addEventListener("mouseup", function () { drag = null; });
    window.addEventListener("mousemove", function (e) { if (!drag) return; var dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY;
      if (drag.pan) { S.pan[0] += dx; S.pan[1] += dy; } else { S.yaw -= dx * 0.008; S.pitch = Math.max(-1.5708, Math.min(1.5708, S.pitch + dy * 0.008)); } if (!S.play) pintar(); });
    cv.addEventListener("wheel", function (e) { e.preventDefault(); S.zoom *= e.deltaY < 0 ? 1.12 : 1 / 1.12; if (!S.play) pintar(); }, { passive: false });
    fit(); modo(0); actual = { solo: solo, modo: modo, vista: vista };
    // para grabar vídeo: HKMODOS.fotograma(modo, fase -1..1, yaw, pitch) deja la estructura quieta en esa fase
    HM.fotograma = function (k, fase, yaw, pitch) { S.play = false; S.fase = fase; if (yaw != null) { S.yaw = yaw; S.pitch = pitch; fit(); } modo(k); pintar(); };
    HM.girar = function (yaw, pitch) { S.yaw = yaw; S.pitch = pitch; fit(); pintar(); };
    requestAnimationFrame(loop);
    root._hk = { solo: solo, modo: modo };
  };
})();
