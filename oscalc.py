#!/usr/bin/env python3
"""Hekatan OpenSees — CLI que RENDERIZA un script de OpenSees (Tcl) a un reporte HTML.

Corre el script con el motor Hekatan OpenSees (la DLL de Petracca y Camata en un interprete Tcl
embebido: Tcl real -> comandos OpenSees), captura la salida (puts) y arma un reporte
estilo Calcpad: el script a la izquierda + los resultados a la derecha.

Uso:  python oscalc.py modelo.tcl [salida.html]
"""
import sys
import os
import io
import re
import math
import json
import html
import base64
import contextlib


# ---------------------------------------------------------------------------
# Traduccion de materiales "plugin" de STKO (los UNICOS no built-in en OpenSees)
# a sus equivalentes estandar YA compilados en openseespy:
#   DamageTC3D  ->  ASDConcrete3D   (mismo modelo dano-plasticidad, Petracca/ASDEA)
# STKO los emite como  'nDMaterial plugin <tag> pdm DamageTC3D <-clave valor...>'.
# Las curvas Te/Ts/Td (traccion) y Ce/Cs/Cd (compresion) se construyen con las
# MISMAS funciones que STKO usa dentro de ASDConcrete3D.py (portadas 1:1).
# ---------------------------------------------------------------------------
def _is_number(s):
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _bezier3(xi, x0, x1, x2, y0, y1, y2):
    A = x0 - 2.0 * x1 + x2
    B = 2.0 * (x1 - x0)
    C = x0 - xi
    if abs(A) < 1.0e-12:
        x1 = x1 + 1.0e-6 * (x2 - x0)
        A = x0 - 2.0 * x1 + x2
        B = 2.0 * (x1 - x0)
        C = x0 - xi
    if A == 0.0:
        return 0.0
    D = B * B - 4.0 * A * C
    t = (math.sqrt(D) - B) / (2.0 * A)
    return (y0 - 2.0 * y1 + y2) * t * t + 2.0 * (y1 - y0) * t + y0


def _get_lch_ref(E, ft, Gt, fc, ec, Gc):
    """Longitud caracteristica de referencia para la energia de fractura especifica."""
    et_el = ft / E
    Gt_min = ft * et_el / 2.0
    hmin_t = Gt / Gt_min / 100.0
    ec1 = fc / E
    ec_pl = (ec - ec1) * 0.4 + ec1
    Gc_min = fc * (ec - ec_pl) / 2.0
    hmin_c = Gc / Gc_min / 100.0
    return min(hmin_t, hmin_c)


def _make_tension_bilin(E, ft, Gt, pscale):
    """Ley trilineal endurecimiento-ablandamiento en traccion (Te, Ts, Td)."""
    f0 = ft * 0.9
    f1 = ft
    e0 = f0 / E
    e1 = ft / E * 1.5
    ep = e1 - ft / E
    f2 = 0.2 * ft
    f3 = 1.0e-3 * ft
    w2 = Gt / ft
    w3 = w2 / 0.2
    e2 = w2 + f2 / E + ep
    if e2 <= e1:
        e2 = e1 * 1.001
    e3 = w3 + f3 / E + ep
    if e3 <= e2:
        e3 = e2 * 1.001
    e4 = e3 * 10.0
    Te = [0.0, e0, e1, e2, e3, e4]
    Ts = [0.0, f0, f1, f2, f3, f3]
    Td = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    Tpl = [0.0, 0.0, ep, e2 * 0.9, e3 * 0.8, e3 * 0.8]
    if 0.0 <= pscale < 1.0:
        for i in range(len(Tpl)):
            Tpl[i] = Tpl[i] * pscale
    for i in range(2, len(Te)):
        xi = Te[i]
        si = Ts[i]
        xipl = min(Tpl[i], xi - si / E)
        qi = (xi - xipl) * E
        Td[i] = 1.0 - si / qi
    return (Te, Ts, Td)


def _make_compression(E, fc, fc0, fcr, ec, Gc, pscale):
    """Endurecimiento cuadratico + ablandamiento lineal en compresion (Ce, Cs, Cd)."""
    ec0 = fc0 / E
    ec1 = fc / E
    ec_pl = (ec - ec1) * 0.4 + ec1
    Gc1 = fc * (ec - ec_pl) / 2.0
    Gc2 = max(Gc1 * 1.0e-2, Gc - Gc1)
    ecr = ec + 2.0 * Gc2 / (fc + fcr)
    Ce = [0.0, ec0]
    Cs = [0.0, fc0]
    Cpl = [0.0, 0.0]
    nc = 10
    dec = (ec - ec0) / (nc - 1)
    for i in range(nc - 1):
        iec = ec0 + (i + 1.0) * dec
        Ce.append(iec)
        Cs.append(_bezier3(iec, ec0, ec1, ec, fc0, fc, fc))
        Cpl.append(Cpl[-1] + (iec - Cpl[-1]) * 0.7)
    Ce.append(ecr)
    Cs.append(fcr)
    Cpl.append(Cpl[-1] + (ecr - Cpl[-1]) * 0.7)
    Ce.append(ecr + ec0)
    Cs.append(fcr)
    Cpl.append(Cpl[-1])
    if 0.0 <= pscale < 1.0:
        for i in range(len(Cpl)):
            Cpl[i] = Cpl[i] * pscale
    Cd = [0.0] * len(Ce)
    for i in range(2, len(Ce)):
        xi = Ce[i]
        si = Cs[i]
        xipl = min(Cpl[i], xi - si / E)
        qi = (xi - xipl) * E
        Cd[i] = 1.0 - si / qi
    return (Ce, Cs, Cd)


def damagetc3d_to_asdconcrete3d(tag, p):
    """Mapea los parametros de un DamageTC3D (dict clave->valor) a los argumentos
    openseespy de un ASDConcrete3D equivalente. Devuelve la lista de args lista
    para  ops.nDMaterial(*args)."""
    g = lambda k, d=None: float(p[k]) if k in p and p[k] is not None else d
    E = g('E'); nu = g('nu', 0.2)
    ft = g('ft'); Gt = g('Gt')
    fc = g('fcp'); fc0 = g('fc0'); fcr = g('fcr'); ec = g('ep'); Gc = g('Gc')
    # pdf_t/pdf_c (factor plastico-dano de DamageTC3D) == pscale de plasticidad
    pdf_t = g('pdf_t', 0.0); pdf_c = g('pdf_c', 0.7)
    rho = g('rho', 0.0); eta = g('eta', 0.0); Kc = g('Kc', 2.0 / 3.0)
    auto = int(g('autoRegularization', 1))
    implex = int(g('implex', 0))
    ctype = int(g('constitutiveTensorType', 0))  # 0 Tangent, 1 TangentPert, 2 Secant
    if auto:
        lch_ref = _get_lch_ref(E, ft, Gt, fc, ec, Gc)
        gt, gc = Gt / lch_ref, Gc / lch_ref
    else:
        lch_ref, gt, gc = None, Gt, Gc
    Te, Ts, Td = _make_tension_bilin(E, ft, gt, pdf_t)
    Ce, Cs, Cd = _make_compression(E, fc, fc0, fcr, ec, gc, pdf_c)
    args = ['ASDConcrete3D', int(tag), E, nu,
            '-Te', *Te, '-Ts', *Ts, '-Td', *Td,
            '-Ce', *Ce, '-Cs', *Cs, '-Cd', *Cd,
            '-rho', rho, '-eta', eta, '-Kc', Kc, '-cdf', 0.0]
    if implex:
        args.append('-implex')
    if ctype == 0:
        args.append('-tangent')            # Tangent; si no, ASDConcrete3D usa secante
    if auto:
        args += ['-autoRegularization', lch_ref]
    return args


def run_opensees(tcl_src):
    """Ejecuta un script Tcl de OpenSees y devuelve (salida_puts, error)."""
    # Motor = Hekatan OpenSees: la DLL de Petracca y Camata cargada en un Tcl (hk_ops). Ya trae TODOS los comandos
    # (pattern, section, element, ASDShellQ4...), asi que solo se captura `puts` y se registra el tipo de cada elemento.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import hk_ops as ops
    t = ops._T
    out_buf = []

    def _puts(*args):
        a = list(args)
        nonl = False
        if a and a[0] == '-nonewline':
            nonl = True
            a = a[1:]
        if len(a) >= 2 and a[0] in ('stdout', 'stderr'):   # canal opcional
            a = a[1:]
        out_buf.append((a[0] if a else '') + ('' if nonl else '\n'))
        return ''

    ele_types = {}

    def element(*args):
        # registra el TIPO de cada elemento para dibujar las vigas con interpolacion cubica de Hermite
        if len(args) >= 2:
            try:
                ele_types[int(args[1])] = str(args[0])
            except (ValueError, TypeError):
                pass
        return t.eval('_hk_element ' + ' '.join(('{%s}' % x) if (' ' in str(x) or '\n' in str(x)) else str(x) for x in args))

    def model(*args):
        # `element` solo existe despues de `model basic`: se engancha en ese momento
        r = t.eval('_hk_model ' + ' '.join(str(x) for x in args))
        if t.eval('info commands element'):
            t.eval('catch {rename element _hk_element}')
            t.createcommand('element', element)
        return r

    t.eval('rename model _hk_model')
    t.createcommand('model', model)
    t.createcommand('puts', _puts)        # captura la salida de puts

    err = None
    try:
        t.eval(tcl_src)
    except Exception as e:                # error de Tcl/OpenSees
        err = str(e)

    # Extraer el estado del modelo para dibujar la deformada (si no se hizo wipe al final).
    # La DLL devuelve numeros como float (1.0): las etiquetas se pasan siempre como int.
    def lst(v):
        return [] if v is None else (v if isinstance(v, list) else [v])

    model = None
    try:
        ntags = [int(x) for x in lst(ops.getNodeTags())]
        if ntags:
            ndm = len(lst(ops.nodeCoord(ntags[0])))
            nodes = {n: [float(c) for c in lst(ops.nodeCoord(n))] for n in ntags}
            disps = {n: [float(x) for x in lst(ops.nodeDisp(n))] for n in ntags}
            elems, etypes = [], []
            for e in [int(x) for x in lst(ops.getEleTags())]:
                try:
                    elems.append([int(x) for x in lst(ops.eleNodes(e))])
                    etypes.append(ele_types.get(e, ""))
                except Exception:
                    pass
            model = {"ndm": ndm, "nodes": nodes, "disps": disps,
                     "elems": elems, "etypes": etypes}
    except Exception:
        model = None
    return ''.join(out_buf), err, model


# Estilo Tcl-puro embebido (se inyecta en el CUERPO; convive con el template de Calcpad)
BODY_STYLE = """<script>window._c=window._c||function(l,d){return window.HK_DARK?d:l};if(location.search.indexOf('dark')>=0||%DARK%){window.HK_DARK=true;document.documentElement.className='hkd';}</script><style>
/* ===== Formato de libro: el mismo de los reportes de Hekatan LISP (crema, Segoe UI 11 pt, secciones centradas y numeradas) ===== */
:root{--bg:#FBF7EC;--fg:#171310;--mut:#544d3a;--var:#0b4fa8;--num:#08306b;--sep:#9c86b8;--fig:#FFFDF6;--bord:#d8cfb8;--code:#F3EDDB;--ok:#2b8a3e;--err:#c62828}
html.hkd{--bg:#141109;--fg:#E8E2D4;--mut:#A89F8C;--var:#7fb2ff;--num:#8ec5ff;--sep:#3a3226;--fig:#1a1712;--bord:#3a3226;--code:#1a1712;--ok:#6fd6a0;--err:#ff8a80}
*{box-sizing:border-box}
body{margin:0;padding:10px 1.5em;background:var(--bg);color:var(--fg);font-family:'Segoe UI','Arial Nova',Helvetica,sans-serif;font-size:11pt;line-height:150%;overflow-x:hidden;counter-reset:sec}
h1,h2,h3,h4,h5,h6{font-family:'Segoe UI','Arial Nova',Helvetica,sans-serif;line-height:150%;color:var(--fg)}
h1{font-weight:700;font-size:15pt;text-align:center;margin:.7em 0 .5em}
h2{font-weight:600;font-size:12.5pt;text-align:center;margin:.9em 0 .35em;counter-increment:sec}
h2::before{content:counter(sec) " ·  "}
h3{font-weight:600;font-size:11pt;margin:.6em 0 .25em;color:var(--mut)}
h4{font-weight:600;font-size:10.5pt;margin:.6em 0 .25em;color:var(--mut)}
p,.osdoc{margin:.35em 0;line-height:150%}
b,strong,th{color:var(--fg)}
/* ecuaciones: Georgia, variables en cursiva azul (como .m-var de Hekatan LISP) */
.eq,.matrix{font-family:Georgia,'Times New Roman',Times,serif;font-size:11.5pt;font-variant-numeric:lining-nums}
.eq{margin:.4em 0;padding:.3em 0}
.eq var{font-style:italic;color:var(--var);font-size:105%}
.eq i{color:var(--num);font-style:normal;font-size:90%}
.eq b{font-weight:600}
.eq sub{font-family:Calibri,Candara,Corbel,sans-serif;font-size:80%;vertical-align:-18%;margin-left:1pt}
.eq sup{display:inline-block;margin-left:1pt;margin-top:-3pt;font-size:75%}
/* matrices con corchetes, números en azul oscuro */
.matrix{display:inline-table;vertical-align:middle;margin:4pt 6pt}
.matrix .tr{display:table-row}
.matrix .td{white-space:nowrap;padding:0 6pt;min-width:10pt;display:table-cell;font-size:10pt;text-align:right;color:var(--num)}
.matrix .td:first-child,.matrix .td:last-child{width:.75pt;min-width:.75pt;max-width:.75pt;padding:0 1pt}
.matrix .td:first-child{border-left:solid 1.2pt var(--fg)}
.matrix .td:last-child{border-right:solid 1.2pt var(--fg)}
.matrix .tr:first-child .td:first-child,.matrix .tr:first-child .td:last-child{border-top:solid 1.2pt var(--fg)}
.matrix .tr:last-child .td:first-child,.matrix .tr:last-child .td:last-child{border-bottom:solid 1.2pt var(--fg)}
/* figuras: centradas, con su pie «Título · detalle» pequeño y gris */
.osdefwrap,.osvtkwrap{position:relative;display:block;margin:.6em auto 1em;text-align:center}
.osdefwrap canvas{border:1px solid var(--bord);background:var(--fig);border-radius:4px;max-width:100%}
.osvtk{width:660px;max-width:100%;height:420px;border:1px solid var(--bord);background:var(--fig);border-radius:4px;position:relative;margin:0 auto}
.osvtip{position:absolute;pointer-events:none;display:none;background:var(--fig);border:1px solid var(--bord);border-radius:5px;padding:4px 7px;font:10px/1.35 'Cascadia Code',Consolas,monospace;color:var(--fg);box-shadow:0 1px 4px rgba(0,0,0,.25)}
canvas{border-color:var(--bord)}
.hk-cap{font-family:'Segoe UI',sans-serif;font-size:10pt;color:var(--fg);margin:.3em 0 .6em;text-align:center}
.hk-cap span{color:var(--mut);font-size:.92em}
/* bloques propios de Hekatan OpenSees (código y salida): Cascadia, fondo suave */
.osblk{font:10.5pt/1.5 'Cascadia Code',Consolas,monospace;background:var(--code);border:1px solid var(--bord);border-radius:6px;padding:10px 14px;white-space:pre;overflow:auto;margin:.4em 0}
.osblk .cmt{color:var(--ok);font-style:italic}
.osblk .kw{color:#cf222e;font-weight:600}
.osblk .num{color:var(--num)}
.osout{font:10.5pt/1.5 'Cascadia Code',Consolas,monospace;color:var(--num);white-space:pre-wrap;margin:4px 0}
.oserr{color:var(--err);background:var(--code);border:1px solid var(--err);border-radius:6px;padding:8px 10px;margin-top:6px;white-space:pre-wrap}
.osh{font-family:'Segoe UI',sans-serif;margin:.7em 0 .3em;font-weight:600;font-size:12.5pt;line-height:150%;color:var(--fg);text-align:center}
.osh{counter-increment:sec}
.osh::before{content:counter(sec) " · "}
.osh.nonum{counter-increment:none}
.osh.nonum::before{content:""}
h4{text-align:center;color:var(--fg)}
/* tablas estilo libro técnico (booktabs): regla arriba y abajo del encabezado, filita fina entre datos */
table{border-collapse:collapse;font-size:10.3pt;margin:.5em auto .9em}
table thead tr,table tr:first-child{border-top:1.4px solid var(--fg)}
table th{font-weight:700;border-bottom:1.4px solid var(--fg);padding:.3em .85em;white-space:nowrap;text-align:left}
table td{padding:.26em .85em;border-bottom:.75px solid var(--sep);white-space:nowrap}
table tr:last-child td{border-bottom:1.4px solid var(--fg)}
.pagebreak{break-before:page;page-break-before:always;height:0;margin:0;border:0}
@media print{body{background:#fff}h1,h2,h3{break-after:avoid;page-break-after:avoid}.matrix,.eq{break-inside:avoid}}
</style>"""


def _body_style():
    import ecuacion
    return BODY_STYLE.replace('</style>', ecuacion.CSS + '</style>').replace('%DARK%', 'true' if os.environ.get('HK_TEMA') == 'dark' else 'false')

def plotly_lib(src):
    """Plotly (3.5 MB) solo si el guion lo usa: un bloque #gfx con plotly(...), plotlyPlot(...), plotlySurf(...)."""
    if 'plotly' not in (src or ''):
        return ''
    d = os.path.dirname(os.path.abspath(__file__))
    try:
        lib = open(os.path.join(d, 'plotly-2.35.2.min.js'), encoding='utf-8').read()
        glue = open(os.path.join(d, 'plotly_gfx.js'), encoding='utf-8').read()
    except OSError:
        return ''
    return '<script>' + lib + '</script><script>' + glue + '</script>'



KW = {"model", "node", "fix", "element", "section", "nDMaterial", "uniaxialMaterial",
      "geomTransf", "timeSeries", "pattern", "load", "eleLoad", "sp", "mass",
      "system", "numberer", "constraints", "integrator", "algorithm", "analysis",
      "analyze", "recorder", "puts", "set", "expr", "for", "foreach", "if", "wipe",
      "nodeDisp", "eleResponse", "reactions", "nodeReaction", "region", "rigidDiaphragm",
      "eigen", "wipeAnalysis", "print", "loadConst", "rigidLink", "equalDOF"}


def hl(cmd):
    """Resaltado Tcl: primer token (comando) en rojo, numeros en azul."""
    parts = cmd.split(' ', 1)
    head = parts[0]
    out = (f'<span class="kw">{html.escape(head)}</span>' if head in KW else html.escape(head))
    if len(parts) > 1:
        rest = re.sub(r'(?<![\w.])(-?\d+\.?\d*)', r'<span class="num">\1</span>', html.escape(parts[1]))
        out += ' ' + rest
    return out


DEFORMED_JS = r"""
(function(){
 var D=__DATA__; if(!D||!D.nodes)return;
 var N=D.nodes,U=D.disps,E=D.elems||[],T=D.etypes||[],m=D.ndm,K=Object.keys(N);
 function P(c){return m>=3?[c[0]-0.5*c[2],c[1]+0.35*c[2]]:[c[0],c[1]];}
 function isBeam(i){return m==2 && /beam/i.test(T[i]||"");}
 function dm(k){var d=U[k]||[];return Math.hypot(d[0]||0,d[1]||0,(m>=3?(d[2]||0):0));}
 var mnx=1e9,mxx=-1e9,mny=1e9,mxy=-1e9;
 K.forEach(function(k){var p=P(N[k]);mnx=Math.min(mnx,p[0]);mxx=Math.max(mxx,p[0]);mny=Math.min(mny,p[1]);mxy=Math.max(mxy,p[1]);});
 var sz=Math.max(mxx-mnx,mxy-mny)||1,md=0;K.forEach(function(k){md=Math.max(md,dm(k));});
 var sf=md>0?0.16*sz/md:0;
 function Dn(k){var c=N[k],d=U[k]||[];return [c[0]+sf*(d[0]||0),c[1]+sf*(d[1]||0),(m>=3?c[2]+sf*(d[2]||0):0)];}
 // VIGA 2D: deformada por interpolacion CUBICA de Hermite (usa traslacion y giro de ambos extremos).
 // beamSamples devuelve cada muestra con su desplazamiento, para hover en CUALQUIER punto.
 function beamSamples(ni,nj){
  var ci=N[ni],cj=N[nj],di=U[ni]||[],dj=U[nj]||[];
  var dx=cj[0]-ci[0],dy=cj[1]-ci[1],L=Math.hypot(dx,dy)||1,cs=dx/L,sn=dy/L;
  var ai=(di[0]||0)*cs+(di[1]||0)*sn,vi=-(di[0]||0)*sn+(di[1]||0)*cs,ti=di[2]||0;
  var aj=(dj[0]||0)*cs+(dj[1]||0)*sn,vj=-(dj[0]||0)*sn+(dj[1]||0)*cs,tj=dj[2]||0;
  var arr=[],nn=16,s,x,a,v,gx,gy;
  for(s=0;s<=nn;s++){x=s/nn;
   a=(1-x)*ai+x*aj;
   v=(1-3*x*x+2*x*x*x)*vi+L*(x-2*x*x+x*x*x)*ti+(3*x*x-2*x*x*x)*vj+L*(-x*x+x*x*x)*tj;
   gx=a*cs-v*sn;gy=a*sn+v*cs;
   arr.push({p:[ci[0]+x*dx+sf*gx,ci[1]+x*dy+sf*gy],u:[gx,gy],node:(s==0?ni:(s==nn?nj:null)),st:x*L});}
  return arr;
 }
 function elemSamples(e,i){return (isBeam(i)&&e.length==2)?beamSamples(e[0],e[1]):e.map(function(k){return {p:Dn(k),u:(U[k]||[]),node:k,st:null};});}
 var SAMP=[];E.forEach(function(e,i){SAMP=SAMP.concat(elemSamples(e,i));});
 SAMP.forEach(function(o){var q=P(o.p);mnx=Math.min(mnx,q[0]);mxx=Math.max(mxx,q[0]);mny=Math.min(mny,q[1]);mxy=Math.max(mxy,q[1]);});
 var cv=document.getElementById("osdef"),cx=cv.getContext("2d"),W=cv.width,H=cv.height,pd=34;
 var sc=Math.min((W-2*pd)/(mxx-mnx||1),(H-2*pd)/(mxy-mny||1));
 function S(p){var q=P(p);return [pd+(q[0]-mnx)*sc,H-pd-(q[1]-mny)*sc];}
 function jet(t){t=Math.max(0,Math.min(1,t));var u=1-t;function f(z){return Math.round(255*Math.max(0,Math.min(1,1.5-Math.abs(4*u-z))));}return "rgb("+f(3)+","+f(2)+","+f(1)+")";}
 function line(pts,col,wd){cx.strokeStyle=col;cx.lineWidth=wd;cx.beginPath();var a=S(pts[0]);cx.moveTo(a[0],a[1]);for(var i=1;i<pts.length;i++){var b=S(pts[i]);cx.lineTo(b[0],b[1]);}cx.stroke();}
 function drawBase(){cx.clearRect(0,0,W,H);
  E.forEach(function(e){line(e.map(function(k){return N[k];}),_c("#c4c8cc","#4a4234"),1);});
  E.forEach(function(e,i){line(elemSamples(e,i).map(function(o){return o.p;}),jet(md>0?(dm(e[0])+dm(e[e.length-1]))/2/md:0),2.6);});
  K.forEach(function(k){var p=S(Dn(k));cx.fillStyle=_c("#333","#e8e2d4");cx.beginPath();cx.arc(p[0],p[1],3,0,6.2832);cx.fill();});
  cx.fillStyle=_c("#999","#8a8272");cx.font="10px Segoe UI";cx.fillText("gris = sin deformar  -  color = deformada (x"+Math.round(0.16*sz/(md||1e9))+")",8,H-8);}
 drawBase();
 var tip=document.getElementById("ostip");
 function fx(v){return (v||0).toExponential(2);}
 // HOVER en cualquier punto: marca la muestra mas cercana de la deformada (sigue el cursor)
 cv.onmousemove=function(ev){var r=cv.getBoundingClientRect(),mx=(ev.clientX-r.left)*W/r.width,my=(ev.clientY-r.top)*H/r.height,best=null,bd=1e18,bp=null;
  SAMP.forEach(function(o){var p=S(o.p),dx=p[0]-mx,dy=p[1]-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=o;bp=p;}});
  if(!best){tip.style.display="none";return;}
  drawBase();
  cx.strokeStyle="rgba(120,120,120,.45)";cx.lineWidth=1;cx.beginPath();cx.moveTo(bp[0],0);cx.lineTo(bp[0],H);cx.moveTo(0,bp[1]);cx.lineTo(W,bp[1]);cx.stroke();
  cx.fillStyle=_c("#111","#e8e2d4");cx.beginPath();cx.arc(bp[0],bp[1],4.5,0,6.2832);cx.fill();cx.lineWidth=1.5;cx.strokeStyle=_c("#fff","#1a1712");cx.stroke();
  var lbl=(best.node!=null)?("Nudo "+best.node):("x ≈ "+best.st.toFixed(2)+" m");
  tip.style.display="block";tip.style.left=Math.min(bp[0]+12,W-110)+"px";tip.style.top=bp[1]+"px";
  tip.innerHTML=lbl+"<br>ux = "+fx(best.u[0])+"<br>uy = "+fx(best.u[1])+(m>=3?"<br>uz = "+fx(best.u[2]):"");};
 cv.onmouseleave=function(){drawBase();tip.style.display="none";};
})();
"""


def render_deformed(model):
    """Canvas con la estructura deformada + datatip (hover). Las vigas se dibujan
    con interpolacion cubica de Hermite (curva, horizontal en el empotramiento)."""
    if not model or not model.get("nodes"):
        return ""
    return (''
            '<div class="osdefwrap"><canvas id="osdef" width="660" height="380"></canvas>'
            '<div id="ostip"></div></div>'
            '<script>' + DEFORMED_JS.replace("__DATA__", json.dumps(model)) + '</script>')


# ===================== Motor de gráficas Calcpad (ML 2D / GL3 3D) embebido =====================
_HERE = os.path.dirname(os.path.abspath(__file__))
_ENGINES = None


def engines_script():
    """Inyecta mlplot.js (ML) + glplot.js (GL3) INLINE una sola vez. El mismo motor de
    Calcpad-Symbolic; embebido en el reporte (sin calcpad.local, sin setup.bat)."""
    global _ENGINES
    if _ENGINES is None:
        js = ''
        for f in ('mlplot.js', 'glplot.js', 'matlab.js'):
            try:
                js += open(os.path.join(_HERE, f), encoding='utf-8').read() + '\n'
            except Exception:
                pass
        _ENGINES = ('<script>' + js + '</script>') if js else ''
    return _ENGINES


_ENGINES_VTK = None


def engines_vtk():
    """Inyecta vtk.js (UMD offline, ~2.6 MB) + osvtk.js INLINE, una sola vez. Solo se llama
    para modelos 3D (ndm==3), así los reportes 2D no cargan la librería. 100% offline/GPU."""
    global _ENGINES_VTK
    if _ENGINES_VTK is None:
        js = ''
        for f in ('vtk_umd.js', 'osvtk.js'):
            try:
                js += open(os.path.join(_HERE, f), encoding='utf-8').read() + '\n'
            except Exception:
                pass
        _ENGINES_VTK = ('<script>' + js + '</script>') if js else ''
    return _ENGINES_VTK


def _jet_hex(t):
    t = max(0.0, min(1.0, t))
    u = 1 - t
    def c(z):
        return max(0.0, min(1.0, 1.5 - abs(4 * u - z)))
    return '#%02x%02x%02x' % (round(c(3) * 255), round(c(2) * 255), round(c(1) * 255))


def _g(d, i):
    return d[i] if i < len(d) else 0.0


def _beam_pts2d(model, ni, nj, sf):
    """Puntos de la deformada de una viga 2D por Hermite cúbico: (x, y, |u|)."""
    ci, cj = model['nodes'][ni], model['nodes'][nj]
    di, dj = model['disps'].get(ni, []), model['disps'].get(nj, [])
    dx, dy = cj[0] - ci[0], cj[1] - ci[1]
    L = math.hypot(dx, dy) or 1.0
    cs, sn = dx / L, dy / L
    ai, vi, ti = _g(di, 0) * cs + _g(di, 1) * sn, -_g(di, 0) * sn + _g(di, 1) * cs, _g(di, 2)
    aj, vj, tj = _g(dj, 0) * cs + _g(dj, 1) * sn, -_g(dj, 0) * sn + _g(dj, 1) * cs, _g(dj, 2)
    out, nn = [], 12
    for s in range(nn + 1):
        x = s / nn
        a = (1 - x) * ai + x * aj
        v = (1 - 3*x*x + 2*x*x*x) * vi + L*(x - 2*x*x + x*x*x) * ti \
            + (3*x*x - 2*x*x*x) * vj + L*(-x*x + x*x*x) * tj
        gx, gy = a * cs - v * sn, a * sn + v * cs
        out.append((ci[0] + x*dx + sf*gx, ci[1] + x*dy + sf*gy, math.hypot(gx, gy)))
    return out


def _elem_def_pts(model, e, etype, sf):
    is_beam = ('beam' in (etype or '').lower()) and len(e) == 2 and model.get('ndm', 2) == 2
    if is_beam:
        return _beam_pts2d(model, e[0], e[1], sf)
    pts = []
    for k in e:
        c, d = model['nodes'][k], model['disps'].get(k, [])
        pts.append((c[0] + sf*_g(d, 0), c[1] + sf*_g(d, 1), math.hypot(_g(d, 0), _g(d, 1))))
    return pts


def render_vtk3d(model, gid='osv0'):
    """Deformada 3D ORBITABLE con vtk.js (GPU, estilo STKO): frames como líneas, shells/bricks
    como caras, color jet_r por |u|, estructura sin deformar en gris fantasma, triada + hover.
    Devuelve el contenedor + los datos como OSVTK_DATA; requiere engines_vtk() en la página."""
    nodes, disps, elems = model['nodes'], model['disps'], model['elems']
    etypes = model.get('etypes', [])
    keys = sorted(nodes.keys())
    idx = {k: i for i, k in enumerate(keys)}

    def _z(c):
        return c[2] if len(c) > 2 else 0.0

    xs = [nodes[k][0] for k in keys]
    ys = [nodes[k][1] for k in keys]
    zs = [_z(nodes[k]) for k in keys]
    size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
    maxd = 0.0
    for k in keys:
        d = disps.get(k, [])
        maxd = max(maxd, math.sqrt(_g(d, 0) ** 2 + _g(d, 1) ** 2 + _g(d, 2) ** 2))
    sf = 0.12 * size / maxd if maxd > 0 else 0.0

    pts, pts0, umag, uvec = [], [], [], []
    for k in keys:
        c, d = nodes[k], disps.get(k, [])
        x, y, z = c[0], c[1], _z(c)
        ux, uy, uz = _g(d, 0), _g(d, 1), _g(d, 2)
        pts0 += [x, y, z]
        pts += [x + sf * ux, y + sf * uy, z + sf * uz]
        umag.append(math.sqrt(ux * ux + uy * uy + uz * uz))
        uvec.append([ux, uy, uz])

    # Caras de referencia: hexaedro (6 quads) y tetraedro (4 triángulos), nodos de esquina.
    HEX_F = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    TET_F = [[0, 2, 1], [0, 1, 3], [1, 2, 3], [2, 0, 3]]
    # Los SÓLIDOS aportan solo su PIEL exterior (cara que aparece 1 vez; las compartidas
    # entre 2 elementos son internas → se descartan). Sirve para malla regular E irregular
    # (hex/tet/mixta): la conectividad es topológica, la geometría puede ser arbitraria.
    lines = []
    surf_faces = []            # elementos SUPERFICIE (cáscaras): se dibujan siempre
    solid_faces = {}           # clave = nodos ordenados → cara; None = interna (descartada)

    def add_solid(face):
        k = tuple(sorted(face))
        solid_faces[k] = None if k in solid_faces else face

    for e_i, e in enumerate(elems):
        ii = [idx[n] for n in e if n in idx]
        n = len(ii)
        et = (etypes[e_i] if e_i < len(etypes) else '').lower()
        is_tet = ('tet' in et)
        is_hex = ('brick' in et) or ('hex' in et) or (et == '' and n in (8, 20))
        is_shell = ('shell' in et) or ('quad' in et) or ('tri' in et) or ('membrane' in et)
        if n == 2:
            lines += [2, ii[0], ii[1]]
        elif is_tet and n >= 4:                  # tetraedro sólido → 4 caras triangulares
            c = ii[:4]
            for f in TET_F:
                add_solid([c[j] for j in f])
        elif is_hex and n >= 8:                  # hexaedro sólido → 6 caras quad
            c = ii[:8]
            for f in HEX_F:
                add_solid([c[j] for j in f])
        elif is_shell and n in (3, 4):           # cáscara → una cara
            surf_faces.append(ii[:n])
        elif n == 3:                             # 3 nodos sin tipo: cara triangular
            surf_faces.append(ii[:3])
        elif n == 4:                             # 4 nodos sin tipo: cara quad (cáscara)
            surf_faces.append(ii[:4])
        elif n == 8:                             # 8 nodos sin tipo: sólido hex por defecto
            c = ii[:8]
            for f in HEX_F:
                add_solid([c[j] for j in f])
        elif n >= 2:                             # genérico: recorrido de aristas
            for a in range(n - 1):
                lines += [2, ii[a], ii[a + 1]]

    polys = []
    for f in surf_faces:
        polys += [len(f)] + f
    for k, f in solid_faces.items():
        if f is not None:
            polys += [len(f)] + f

    data = {"gid": gid, "pts": pts, "pts0": pts0, "umag": umag, "uvec": uvec,
            "lines": lines, "polys": polys, "tags": keys, "umax": maxd, "sf": sf}
    return ('<div class="osvtkwrap"><div id="%s" class="osvtk"></div>'
            '<div id="%s_tip" class="osvtip"></div></div>'
            '<script>window.osvtkMount(%s);</script>'
            % (gid, gid, json.dumps(data)))


def render_plot(model, gid='osp0'):
    """Deformada con el MOTOR de Calcpad (ML 2D). Vigas con Hermite, color jet por |u|,
    hover (datatip/datapoint) y colorbar — igual que Calcpad-Symbolic, sin $plot/$map/'<>'.
    Para 3D (ndm==3) usa el visor vtk.js ORBITABLE (render_vtk3d)."""
    if not model or not model.get('nodes'):
        return render_deformed(model)
    if model.get('ndm', 2) == 3:
        return render_vtk3d(model, gid.replace('osp', 'osv'))
    if model.get('ndm', 2) != 2:
        return render_deformed(model)          # ndm==1: canvas propio
    nodes, disps, elems = model['nodes'], model['disps'], model['elems']
    etypes = model.get('etypes', [])
    keys = sorted(nodes.keys())
    xs = [nodes[k][0] for k in keys]
    ys = [nodes[k][1] for k in keys]
    size = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    maxd = 0.0
    for k in keys:
        maxd = max(maxd, math.hypot(_g(disps.get(k, []), 0), _g(disps.get(k, []), 1)))
    sf = 0.16 * size / maxd if maxd > 0 else 0.0
    segs, bx0, bx1, by0, by1 = [], min(xs), max(xs), min(ys), max(ys)
    for i, e in enumerate(elems):
        pts = _elem_def_pts(model, e, etypes[i] if i < len(etypes) else '', sf)
        segs.append(pts)
        for (px, py, _u) in pts:
            bx0, bx1, by0, by1 = min(bx0, px), max(bx1, px), min(by0, py), max(by1, py)
    mx = (bx1 - bx0) * 0.08 or 1.0
    my = (by1 - by0) * 0.08 or 1.0
    bx0, bx1, by0, by1 = bx0 - mx, bx1 + mx, by0 - my, by1 + my

    js = [f'ML.figure("{gid}",560,400);', f'ML.axis({bx0:.6g},{bx1:.6g},{by0:.6g},{by1:.6g});']
    for e in elems:                            # estructura sin deformar (gris)
        for j in range(len(e) - 1):
            a, b = nodes[e[j]], nodes[e[j + 1]]
            js.append(f'ML.line({a[0]:.6g},{a[1]:.6g},{b[0]:.6g},{b[1]:.6g},_c("#c4c8cc","#4a4234"));')
    for pts in segs:                           # deformada (color jet por |u|)
        for j in range(len(pts) - 1):
            ax, ay, au = pts[j]
            bx, by, bu = pts[j + 1]
            col = _jet_hex(((au + bu) / 2) / maxd if maxd > 0 else 0)
            js.append(f'ML.line({ax:.6g},{ay:.6g},{bx:.6g},{by:.6g},"{col}");')
    js.append('ML.datatip("|u| (m)");')        # hover estilo MATLAB
    for k in keys:
        d = disps.get(k, [])
        js.append(f'ML.datapoint({nodes[k][0]+sf*_g(d,0):.6g},{nodes[k][1]+sf*_g(d,1):.6g},'
                  f'{math.hypot(_g(d,0),_g(d,1)):.6g});')
    js.append(f'ML.colorbar(0,{maxd:.6g});')
    return '<script>' + '\n'.join(js) + '</script>'


def render_body(src, out, err, model, title, show_script=True):
    """Devuelve SOLO el cuerpo HTML (resultados + deformada; opcionalmente el script).
    Lo envuelve el template de Calcpad (o un navegador, si se abre suelto).
    En el WPF show_script=False: el editor ya muestra el script, no se repite —
    así la deformada queda arriba y visible sin scrollear."""
    script_block = ''
    if show_script:
        code = []
        for line in src.splitlines():
            st = line.strip()
            if not st:
                code.append('')
            elif st.startswith('#'):
                code.append(f'<span class="cmt">{html.escape(line.rstrip())}</span>')
            else:
                indent = '&nbsp;' * (len(line) - len(line.lstrip()))
                code.append(indent + hl(st))
        script_block = (f'<h3>OpenSees — {html.escape(title)}</h3>'
                        f'<div class="osblk">{chr(10).join(code)}</div>')

    # Salida puts y variables exportadas (CALCPAD:nombre=valor)
    exports, clean, hkframes, hkmodos = [], [], [], []
    for ln in out.splitlines():
        if ln.startswith('HKMODO '):
            try:
                cab, uu = ln[7:].split('|')
                t = cab.split()
                hkmodos.append({'k': int(t[0]), 'T': float(t[1]), 'u': [float(v) for v in uu.split()]})
            except ValueError:
                pass
            continue
        if ln.startswith('HKFRAME '):
            try:
                cab, uu, dd = ln[8:].split('|')
                t = cab.split()
                hkframes.append({'s': t[0], 'ux': (t[1] if len(t) > 1 else None), 'u': [float(v) for v in uu.split()], 'd': [float(v) for v in dd.split()]})
            except ValueError:
                pass
            continue
        if ln.startswith(('HEKATAN:', 'CALCPAD:')) and '=' in ln:
            k, v = ln[8:].split('=', 1)
            exports.append((k.strip(), v.strip()))
        else:
            clean.append(ln)

    # Desplazamientos nodales como MATRIZ de Calcpad (no números sueltos)
    Umat = render_disp_matrix(model)
    # Exportadas como vector/escalares en notación Calcpad (.eq), compacto
    exp_html = ''
    if exports:
        exp_html = '<p>' + ' &nbsp; '.join(
            f'<span class="eq"><var>{html.escape(k)}</var> = {_corto(v)}</span>' for k, v in exports) + '</p>'
    out_html = f'<div class="osout">{html.escape(chr(10).join(clean).strip())}</div>' if ''.join(clean).strip() else ''
    err_html = f'<div class="oserr">{html.escape(err)}</div>' if err else ''
    res = (Umat + exp_html + out_html)
    # vtk.js solo para modelos 3D (no infla los reportes 2D con 2.6 MB).
    vtk = engines_vtk() if (model and model.get('ndm') == 3 and ('#plot' in (src or '').lower() or show_script)) else ''
    if show_script:
        return (_body_style() + engines_script() + vtk + plotly_lib(src) + script_block
                + ('<h4>Resultados</h4>' + res if res.strip() else '')
                + err_html + render_plot(model, 'osp0') + '<div class="hk-cap"><b>Deformada</b> <span>· color = |u| · pasa el cursor por un nudo · geometría en m</span></div>')
    # Sin script (en el WPF): el reporte se arma por DIRECTIVAS '#...' (comentarios
    # para OpenSees). El script ya esta en el editor; aqui solo lo legible + graficas.
    return _body_style() + engines_script() + vtk + plotly_lib(src) + cad_lib(src) + grieta_lib(src) + modos_lib(src) + render_report(src, out, err, model) + err_html


def _cp_placeholder(code):
    """Marca la posición de un bloque/línea Calcpad. El C# (que tiene el motor Calcpad)
    decodifica el base64, lo corre por _parser y reemplaza el placeholder por el HTML."""
    b = base64.b64encode(code.encode('utf-8')).decode('ascii')
    return '<!--OSCP ' + b + '-->'


# ---------------------------------------------------------------------------------------------
# #dibujar ... #enddibujar : ventana de dibujo 2D/3D estilo Hekatan LISP (cad3d.js). Todas las lineas empiezan con '#'
# (OpenSees las ignora como comentarios). Ordenes, una por linea:
#     modelo [deformada]                 barras, areas y solidos del modelo OpenSees
#     capa NOMBRE                        capa de lo que sigue (BARRAS, AREAS, SOLIDOS, DIBUJO...)
#     linea x1 y1 z1  x2 y2 z2           (con 4 numeros: x y; z = 0)
#     cara x1 y1 z1 ... x4 y4 z4         3DCARA de 3 o 4 puntos
#     circulo x y z r                    circulo en el plano XY
#     caja x y z dx dy dz                paralelepipedo (12 aristas y 6 caras)
#     texto x y z altura "texto"
#     nombre ARCHIVO                     nombre sugerido al guardar DXF/DWG
# ---------------------------------------------------------------------------------------------
def _modelo_ents(model, deformada=False, sf=None):
    """Barras (LINE, capa BARRAS), cascaras (3DFACE, capa AREAS) y solidos (6 3DFACE, capa SOLIDOS) del modelo."""
    ents = []
    if not model:
        return ents
    nodes, disps = model['nodes'], model.get('disps', {})
    if deformada:
        xs = [c[0] for c in nodes.values()]
        ys = [c[1] for c in nodes.values()]
        zs = [(c[2] if len(c) > 2 else 0.0) for c in nodes.values()]
        size = max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)) or 1.0
        maxd = max((math.sqrt(sum(_g(d, k) ** 2 for k in range(3))) for d in disps.values()), default=0.0)
        sf = sf if sf is not None else (0.12 * size / maxd if maxd > 0 else 0.0)

    def P(k):
        c = nodes[k]
        x, y, z = c[0], c[1], (c[2] if len(c) > 2 else 0.0)
        if deformada:
            d = disps.get(k, [])
            x += sf * _g(d, 0)
            y += sf * _g(d, 1)
            z += sf * _g(d, 2)
        return [round(x, 6), round(y, 6), round(z, 6)]

    for e in model['elems']:
        try:
            if len(e) == 2:
                ents.append({'t': 'L', 'a': P(e[0]), 'b': P(e[1]), 'c': 'BARRAS'})
            elif len(e) in (3, 4):
                ents.append({'t': 'F', 'p': [P(k) for k in e], 'c': 'AREAS'})
            elif len(e) == 8:
                q = [P(k) for k in e]
                for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                    ents.append({'t': 'F', 'p': [q[i] for i in f], 'c': 'SOLIDOS'})
        except KeyError:
            continue
    return ents


def _parse_dibujar(lines, model):
    """Las lineas de un bloque #dibujar -> (entidades, nombre)."""
    import shlex
    ents, capa, nombre = [], 'DIBUJO', 'dibujo'

    def nums(a):
        return [float(x) for x in a]

    for ln in lines:
        try:
            tk = shlex.split(ln)
        except ValueError:
            tk = ln.split()
        if not tk:
            continue
        w, a = tk[0].lower(), tk[1:]
        try:
            if w == 'modelo':
                ents += _modelo_ents(model, deformada=bool(a and a[0].lower().startswith('def')))
            elif w == 'capa' and a:
                capa = a[0].upper()
            elif w == 'nombre' and a:
                nombre = a[0]
            elif w == 'linea':
                v = nums(a)
                if len(v) >= 6:
                    ents.append({'t': 'L', 'a': v[0:3], 'b': v[3:6], 'c': capa})
                elif len(v) >= 4:
                    ents.append({'t': 'L', 'a': [v[0], v[1], 0.0], 'b': [v[2], v[3], 0.0], 'c': capa})
            elif w in ('cara', '3dcara'):
                v = nums(a)
                n3 = len(v) in (9, 12)
                step = 3 if n3 else 2
                pts = [[v[i], v[i + 1], v[i + 2] if n3 else 0.0] for i in range(0, len(v) - step + 1, step)]
                if len(pts) >= 3:
                    ents.append({'t': 'F', 'p': pts[:4], 'c': capa})
            elif w == 'circulo':
                v = nums(a)
                ents.append({'t': 'C', 'p': v[0:3] if len(v) >= 4 else [v[0], v[1], 0.0], 'r': v[3] if len(v) >= 4 else v[2], 'c': capa})
            elif w == 'caja':
                x, y, z, dx, dy, dz = nums(a)[:6]
                q = [[x, y, z], [x + dx, y, z], [x + dx, y + dy, z], [x, y + dy, z],
                     [x, y, z + dz], [x + dx, y, z + dz], [x + dx, y + dy, z + dz], [x, y + dy, z + dz]]
                for i, j in ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
                    ents.append({'t': 'L', 'a': q[i], 'b': q[j], 'c': capa})
                for f in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                    ents.append({'t': 'F', 'p': [q[i] for i in f], 'c': capa})
            elif w == 'texto' and len(a) >= 5:
                v = nums(a[:4])
                ents.append({'t': 'T', 'p': v[0:3], 'h': v[3], 's': ' '.join(a[4:]), 'c': capa})
        except (ValueError, IndexError):
            continue
    return ents, nombre


def cad_lib(src):
    """cad3d.js inline una sola vez, y solo si el guion lleva #dibujar."""
    if '#dibujar' not in (src or '').lower():
        return ''
    d = os.path.dirname(os.path.abspath(__file__))
    try:
        js = open(os.path.join(d, 'cad3d.js'), encoding='utf-8').read()
    except OSError:
        return ''
    css = ('.hkcad{position:relative;display:block;width:760px;max-width:100%;margin:.6em auto 1em;border:1px solid var(--bord);border-radius:4px;background:var(--fig)}'
           '.hkcad-bar{display:flex;flex-wrap:wrap;gap:4px;padding:5px 6px;border-bottom:1px solid var(--bord);font-family:Segoe UI,sans-serif}'
           '.hkcad-bar button{font:12px Segoe UI,sans-serif;padding:3px 9px;border:1px solid var(--bord);border-radius:5px;background:var(--bg);color:var(--fg);cursor:pointer}'
           '.hkcad-bar button:hover{border-color:#e5382b}.hkcad-bar button.on{background:#e5382b;color:#fff;border-color:#e5382b}'
           '.hkcad-sep{width:1px;background:var(--bord);margin:0 3px}.hkcad canvas{display:block;width:100%;height:auto;cursor:crosshair;outline:none}'
           '.hkcad-tip{position:absolute;display:none;pointer-events:none;background:var(--bg);border:1px solid var(--bord);border-radius:5px;padding:3px 8px;font:11px Segoe UI,sans-serif;color:var(--fg);z-index:5}'
           '.hkcad-cmd{display:flex;align-items:center;gap:6px;padding:4px 8px;border-top:1px solid var(--bord);font:12px Segoe UI,sans-serif;color:var(--mut)}'
           '.hkcad-cmd input{flex:1;font:12px Cascadia Code,Consolas,monospace;background:var(--bg);color:var(--fg);border:1px solid var(--bord);border-radius:4px;padding:3px 6px}'
           '.hkcad-st{padding:3px 8px;font:11px Segoe UI,sans-serif;color:var(--mut);border-top:1px solid var(--bord)}')
    return '<style>' + css + '</style><script>' + js + '</script>'


_CSS_GR = ('.hkgr{position:relative;display:block;width:760px;max-width:100%;margin:.6em auto .3em;border:1px solid var(--bord);border-radius:4px;background:var(--fig)}'
           '.hkgr canvas{display:block;width:100%;height:auto}'
           '.hkgr-bar{display:flex;align-items:center;gap:10px;padding:5px 8px;border-top:1px solid var(--bord);font:12px Segoe UI,sans-serif;color:var(--fg)}'
           '.hkgr-bar button{font:12px Segoe UI,sans-serif;padding:3px 10px;border:1px solid var(--bord);border-radius:5px;background:var(--bg);color:var(--fg);cursor:pointer}'
           '.hkgr-bar input[type=range]{flex:1}.hkgr-bar .sf{width:56px;font:12px Segoe UI;background:var(--bg);color:var(--fg);border:1px solid var(--bord);border-radius:4px}'
           '.hkgr-tip{position:absolute;display:none;pointer-events:none;background:var(--bg);border:1px solid var(--bord);border-radius:5px;padding:3px 8px;font:11px Segoe UI,sans-serif;color:var(--fg)}'
           '.hkgr-st{padding:3px 8px;font:11px Segoe UI,sans-serif;color:var(--mut);border-top:1px solid var(--bord)}'
           'html.hkgr-solo body>*{display:none !important}'
           'html.hkgr-solo body>.hkgr{display:block !important;position:fixed;left:0;top:0;width:100vw;max-width:none;margin:0;border:0;border-radius:0;z-index:1000;background:var(--fig)}'
           'html.hkgr-solo body{overflow:hidden;padding:0}html.hkgr-solo .hkgr canvas{width:100%;height:auto}')


def grieta_lib(src):
    """grieta.js (la grieta animada) inline, solo si el guion lleva #grieta."""
    if '#grieta' not in (src or '').lower():
        return ''
    d = os.path.dirname(os.path.abspath(__file__))
    try:
        js = open(os.path.join(d, 'grieta.js'), encoding='utf-8').read()
    except OSError:
        return ''
    css = _CSS_GR
    return '<style>' + css + '</style><script>' + js + '</script>'


def _corto(v):
    """Un vector largo exportado (la serie del tiempo-historia, miles de valores) no se escribe entero en el reporte: solo cuantos son."""
    v = v.strip()
    if v.startswith('[') and len(v) > 80:
        return html.escape('[%d valores]' % (v.count(',') + 1))
    return html.escape(v)


def modos_lib(src):
    """modos.js (modos de vibracion animados) inline, solo si el guion lleva #modos."""
    if '#modos' not in (src or '').lower():
        return ''
    d = os.path.dirname(os.path.abspath(__file__))
    try:
        js = open(os.path.join(d, 'modos.js'), encoding='utf-8').read()
    except OSError:
        return ''
    css = ('.hkmod .mb{border-top:0;border-bottom:1px solid var(--bord)}.hkmod .mb button.on{background:#e5382b;color:#fff;border-color:#e5382b}'
           '.hkmod .hkgr-bar label{display:flex;align-items:center;gap:4px}.hkmod canvas{cursor:grab}')
    return '<style>' + _CSS_GR + css + '</style><script>' + js + '</script>'


def _md_inline(t):
    """**negrita**, *cursiva* y `codigo` dentro del texto de un comentario # (como el texto con formato de Hekatan LISP)."""
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<i>\1</i>', t)
    return re.sub(r'`(.+?)`', r'<code>\1</code>', t)


def render_report(src, out, err, model):
    """Arma el reporte recorriendo el .tcl segun DIRECTIVAS. TODAS empiezan con '#',
    asi OpenSees real las trata como COMENTARIOS y corre el script igual; Hekatan OpenSees
    las interpreta. Es la 'funcion para mostrar' que OpenSees no tiene.

      INLINE (una linea):
        #plot        -> muestra la deformada aqui
        #disp #matrix-> muestra la matriz U de desplazamientos aqui
        #values      -> muestra los valores exportados (CALCPAD:) aqui
        #title  X    -> titulo grande
        ## X         -> encabezado          # X -> texto          #-- X -> OCULTO
      BLOQUE (abre/cierra):
        #hide ... #show  -> oculta del reporte todo lo intermedio (OpenSees igual lo corre)
    """
    exports, clean, hkframes, hkmodos = [], [], [], []
    for ln in out.splitlines():
        if ln.startswith('HKMODO '):
            try:
                cab, uu = ln[7:].split('|')
                t = cab.split()
                hkmodos.append({'k': int(t[0]), 'T': float(t[1]), 'u': [float(v) for v in uu.split()]})
            except ValueError:
                pass
            continue
        if ln.startswith('HKFRAME '):
            try:
                cab, uu, dd = ln[8:].split('|')
                t = cab.split()
                hkframes.append({'s': t[0], 'ux': (t[1] if len(t) > 1 else None), 'u': [float(v) for v in uu.split()], 'd': [float(v) for v in dd.split()]})
            except ValueError:
                pass
            continue
        if ln.startswith(('HEKATAN:', 'CALCPAD:')) and '=' in ln:
            k, v = ln[8:].split('=', 1)
            exports.append((k.strip(), v.strip()))
        else:
            clean.append(ln)
    exp_html = ('<p>' + ' &nbsp; '.join(
        f'<span class="eq"><var>{html.escape(k)}</var> = {_corto(v)}</span>'
        for k, v in exports) + '</p>') if exports else ''
    out_html = (f'<div class="osout">{html.escape(chr(10).join(clean).strip())}</div>'
                if ''.join(clean).strip() else '')

    # Resultados de OpenSees disponibles como VARIABLES JS dentro de los bloques #gfx
    def _isnum(v):
        try:
            float(v); return True
        except ValueError:
            return False
    # escalares Y arrays ([...]) exportados quedan como variables JS en los bloques #gfx
    # (asi el script puede graficar curvas: plot(defl, P) de la P-delta, etc.)
    gfx_vars = ''.join(f'var {k}={v};' for k, v in exports if _isnum(v) or v.strip().startswith('['))

    parts, hiding, gn = [], False, [0]
    used = {'plot': False, 'matrix': False, 'values': False}
    cp_buf, cp_hidden = None, False    # bloque Calcpad embebido (#cp ... #endcp)
    gfx_buf, gfx_hidden = None, False  # bloque de graficas MATLAB (#gfx ... #endgfx)
    dib_buf = None                     # bloque de dibujo (#dibujar ... #enddibujar)
    eq_n = [0]                         # numeracion automatica de ecuaciones (#ec ... | #)

    def plot():
        gn[0] += 1
        return render_plot(model, f'osp{gn[0]}')

    for line in src.splitlines():
        s = line.strip()
        if not s.startswith('#'):
            continue
        tok = s.split(None, 1)
        word = tok[0].lower()
        rest = tok[1].strip() if len(tok) > 1 else ''
        # --- DIBUJO 2D/3D (Hekatan LISP): recolectar el bloque hasta #enddibujar ---
        if dib_buf is not None:
            if word in ('#enddibujar', '#findibujo'):
                ents, nom = _parse_dibujar(dib_buf, model)
                gn[0] += 1
                parts.append(f'<div id="hkcad{gn[0]}"></div><script>HKCAD.mount("hkcad{gn[0]}",{{ents:{json.dumps(ents)},nombre:{json.dumps(nom)},vista:{json.dumps('Planta' if (model and model.get('ndm') == 2) else 'Iso SO')}}});</script>')
                dib_buf = None
            else:
                dib_buf.append(s[1:].strip())
            continue
        if word in ('#dibujar', '#dibujo'):
            dib_buf = []
            if rest:
                dib_buf.append(rest)
            continue
        # --- GRAFICAS MATLAB: recolectar el bloque hasta #endgfx ---
        if gfx_buf is not None:
            if word == '#endgfx':
                code = '\n'.join(gfx_buf)
                if not gfx_hidden and code.strip():
                    parts.append('<script>' + gfx_vars + '\n' + code + '</script>')
                gfx_buf = None
            else:
                gfx_buf.append(s[1:].lstrip())             # quita el '#' → linea de grafica MATLAB
            continue
        # --- CALCPAD EMBEBIDO: recolectar el bloque hasta #endcp ---
        if cp_buf is not None:
            if word == '#endcp':
                code = '\n'.join(cp_buf)
                if not cp_hidden and code.strip():
                    parts.append(_cp_placeholder(code))    # C# lo renderiza con _parser
                cp_buf = None
            else:
                cp_buf.append(s[1:].lstrip())              # quita el '#' (y espacios) → línea Calcpad
            continue
        # --- BLOQUE hide/show ---
        if word == '#hide':
            hiding = True;  continue
        if word == '#show':
            hiding = False; continue
        # --- CALCPAD-Symbolic embebido (operaciones simbólicas dentro del .tcl) ---
        if word == '#cp':                                  # abre bloque multilínea
            cp_buf, cp_hidden = [], hiding; continue
        if word == '#gfx':                                 # abre bloque de graficas MATLAB
            used['plot'] = used['matrix'] = True            # el guion arma su propio reporte: sin deformada ni matriz U automaticas al final
            gfx_buf, gfx_hidden = [], hiding; continue
        if s.startswith('#=') and not s.startswith('#=='):  # inline: '#= expr'
            if not hiding and s[2:].strip():
                parts.append(_cp_placeholder(s[2:].strip()))
            continue
        # --- GRAFICAS estilo Calcpad ('#$nombre', como el $ de Calcpad-Symbolic) ---
        if word.startswith('#$'):
            g = word[2:]
            if g in ('modo', 'mode', 'contorno', 'contour', 'esfuerzos', 'stress', 'momento', 'cortante', 'reacciones'):
                parts.append(f'<p class="osdoc"><i>(gráfica «{html.escape(g)}» — próximamente)</i></p>')
            else:                          # deformada / plot / malla / default
                parts.append(plot()); used['plot'] = True
            continue
        # --- INLINE: 'funciones para mostrar' ---
        if word in ('#plot', '#deformed', '#deformada'):
            parts.append(plot()); used['plot'] = True; continue
        if word in ('#disp', '#matrix', '#u'):
            parts.append('<h4>Resultados</h4>' + render_disp_matrix(model)); used['matrix'] = True; continue
        if word in ('#values', '#valores'):
            parts.append(exp_html + out_html); used['values'] = True; continue
        if word in ('#ec', '#eq', '#ecuacion'):   # ecuacion con formato de Hekatan LISP:  #ec  w = P*L^3/(3*E*I) | (1)
            import ecuacion
            f, _, eti = rest.partition('|')
            eq_n[0] += 1
            parts.append(ecuacion.ecuacion_html(f.strip(), ('(%d)' % eq_n[0]) if eti.strip() == '#' else eti.strip()))
            continue
        if word == '#modos':        # modos de vibracion animados (vectores propios que imprimio el guion: HKMODO)
            if hkmodos and model:
                ids = sorted(i for i in model['nodes'].keys() if i < 10000)
                pos = {i: k for k, i in enumerate(ids)}
                nodes = [(model['nodes'][i] + [0.0, 0.0])[:3] for i in ids]
                bars = [[pos[e[0]], pos[e[1]]] for e in model['elems'] if len(e) == 2 and e[0] in pos and e[1] in pos]
                quads = [[pos[k] for k in e] for e in model['elems'] if len(e) == 4 and all(k in pos for k in e)]
                gn[0] += 1
                dat = {'nodes': nodes, 'bars': bars, 'quads': quads, 'modes': hkmodos}
                parts.append(f'<div id="hkmod{gn[0]}"></div><script>HKMODOS.mount("hkmod{gn[0]}",{json.dumps(dat)});</script>')
                used['plot'] = used['matrix'] = True
            else:
                parts.append('<div class="oserr">#modos: el guion no imprimio modos (HKMODO)</div>')
            continue
        if word == '#grieta':       # la grieta animada: cuadros HKFRAME del analisis (daño a tracción por elemento)
            if hkframes and model:
                ids = sorted(model['nodes'].keys())
                nodes = [model['nodes'][i][:2] for i in ids if i < 10000]
                quads = [e for e in model['elems'] if len(e) == 4]
                gn[0] += 1
                tk = rest.split()
                num = [t for t in tk if t.replace('.', '', 1).isdigit()]
                dat = {'nodes': nodes, 'quads': quads, 'frames': hkframes, 'sf': float(num[0]) if num else 40, 'solo': 'solo' in [t.lower() for t in tk]}
                used['plot'] = used['matrix'] = True      # sin la deformada ni la matriz U de 895 nudos al final
                parts.append(f'<div id="hkgr{gn[0]}"></div><script>HKGRIETA.mount("hkgr{gn[0]}",{json.dumps(dat)});</script>')
            else:
                parts.append('<div class="oserr">#grieta: el guion no imprimio cuadros HKFRAME</div>')
            continue
        if word == '#fig':          # pie de figura:  #fig Titulo | detalle
            t, _, det = rest.partition('|')
            parts.append('<div class="hk-cap"><b>' + html.escape(t.strip()) + '</b>' + (' <span>· ' + html.escape(det.strip()) + '</span>' if det.strip() else '') + '</div>')
            continue
        if word == '#resumen':      # cierre «En una línea» de un reporte-libro
            parts.append('<div class="osh nonum">En una línea</div><div class="osdoc">' + _md_inline(html.escape(rest)) + '</div>')
            continue
        if word == '#title':
            if rest:
                parts.append(f'<h1>{html.escape(rest)}</h1>')
            continue
        if s.startswith('#--'):
            continue                       # oculto inline (OpenSees: comentario)
        if hiding:
            continue                       # dentro de #hide...#show
        # --- comentarios visibles ---
        if s.startswith('##'):
            if s[2:].strip():
                parts.append(f'<div class="osh">{html.escape(s[2:].strip())}</div>')
        elif s[1:].strip():
            parts.append('<div class="osdoc">' + _md_inline(html.escape(s[1:].strip())) + '</div>')

    # Defaults: lo que NO se llamo explicito va al final (deformada, matriz, valores)
    tail = ''
    if not used['plot']:
        tail += plot() + '<div class="hk-cap"><b>Deformada</b> <span>· color = |u| · pasa el cursor por un nudo · geometría en m</span></div>'
    if not used['matrix']:
        tail += '<h4>Resultados</h4>' + render_disp_matrix(model)
    if not used['values']:
        tail += exp_html + out_html
    return ''.join(parts) + tail


def _fmt(v):
    a = abs(v)
    if a < 1e-12:
        return "0"
    if a >= 1e4 or a < 1e-4:
        return f"{v:.3e}"
    return f"{v:.5g}"


def cp_matrix(rows):
    """Matriz en el formato nativo de Calcpad: <span class='matrix'> con celdas
    vacías a los lados que el CSS convierte en corchetes altos."""
    out = ['<span class="matrix">']
    for r in rows:
        out.append('<span class="tr"><span class="td"></span>')
        for c in r:
            out.append(f'<span class="td">{c}</span>')
        out.append('<span class="td"></span></span>')
    out.append('</span>')
    return ''.join(out)


def render_disp_matrix(model):
    """Desplazamientos nodales U como matriz Calcpad: fila = nudo, columnas = nudo + DOF."""
    if not model or not model.get("disps"):
        return ''
    ndm = model.get("ndm", 2)
    keys = sorted(model["nodes"].keys())
    ndof = max((len(model["disps"].get(n, [])) for n in keys), default=0)
    if ndof == 0 or not keys:
        return ''
    trans = ['ux', 'uy', 'uz'][:ndm]
    rot = (['θ'] if ndm == 2 else ['rx', 'ry', 'rz'])
    labels = (trans + rot)[:ndof]
    header = ['<b>nudo</b>'] + [f'<b>{l}</b>' for l in labels]
    rows = [header]
    keys = [n for n in keys if n < 10000]          # los nudos de tierra de los muelles (ids >= 10000) no son del modelo
    mostrar = keys if len(keys) <= 30 else keys[:12] + [None] + keys[-6:]
    for n in mostrar:
        if n is None:
            rows.append(['<b>⋮</b>'] + ['⋮'] * ndof)
            continue
        d = model["disps"].get(n, [])
        rows.append([f'<b>{n}</b>'] + [_fmt(d[k]) if k < len(d) else '0' for k in range(ndof)])
    nota = '' if len(keys) <= 30 else f' &nbsp; <i>(de {len(keys)} nudos se muestran 18; <code>#disp</code> y la deformada los tienen todos)</i>'
    return ('<p>Desplazamientos nodales &nbsp; <span class="eq"><b>U</b></span> &nbsp;'
            '(fila = nudo):' + nota + '</p>' + cp_matrix(rows))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if not args:
        print("uso: python oscalc.py modelo.tcl [salida.html] [--report-only]")
        sys.exit(1)
    inp = args[0]
    outp = args[1] if len(args) > 1 else os.path.splitext(inp)[0] + '.html'
    show_script = '--report-only' not in flags   # WPF lo pasa: el editor ya muestra el script
    src = open(inp, encoding='utf-8').read()
    out, err, model = run_opensees(src)
    open(outp, 'w', encoding='utf-8').write(
        render_body(src, out, err, model, os.path.basename(inp), show_script))
    print('Reporte generado:', outp)
    if err:
        print('  (con error OpenSees:', err, ')')


if __name__ == '__main__':
    main()
