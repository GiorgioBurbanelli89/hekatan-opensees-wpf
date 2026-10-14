# -*- coding: utf-8 -*-
"""Un modelo de Hekatan Struct (el dump .json de un .heks) escrito como guion OpenSees Tcl para Hekatan OpenSees.

    python dump_a_tcl.py dump.json salida.tcl [--asdshell] [--flexion=hekatan] [--titulo "..."]

Es la misma traducción de heks_a_opensees.py (barras ElasticTimoshenkoBeam, cáscaras con ElasticMembranePlateSection,
cargas nodales de Hekatan) pero escrita como Tcl: corre igual en Hekatan OpenSees y en el OpenSees oficial.
El reporte lleva ## títulos, #plot (3D orbitable) y los valores HEKATAN: para corroborar."""
import json, math, sys


def vecxz(nodes, n1, n2):
    """Eje local 3 de CSI (horizontal): Z x eje de la barra; si la barra es vertical, el X global. (= heks_a_opensees.py)"""
    p1, p2 = nodes[n1], nodes[n2]
    dx = [p2[k] - p1[k] for k in range(3)]
    L = math.sqrt(sum(c * c for c in dx))
    ex = [c / L for c in dx]
    ref = [0, 0, 1] if abs(ex[2]) < 0.999 else [1, 0, 0]
    ey = [ref[1] * ex[2] - ref[2] * ex[1], ref[2] * ex[0] - ref[0] * ex[2], ref[0] * ex[1] - ref[1] * ex[0]]
    n = math.sqrt(sum(c * c for c in ey)) or 1.0
    return [c / n for c in ey]


def f(x):
    return repr(float(x))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    dump, out = args[0], args[1]
    titulo = "Galpón 3D"
    if "--titulo" in sys.argv:
        titulo = sys.argv[sys.argv.index("--titulo") + 1]
        args = [a for a in args if a != titulo]
    D = json.load(open(dump, encoding="utf-8"))
    ei, ni, nodes = D["elementInputs"], D["nodeInputs"], D["nodes"]
    g = lambda m, i, d=None: ei.get(m, {}).get(str(i), d) if isinstance(ei.get(m), dict) else d
    elem_shell = "ASDShellQ4" if "--asdshell" in flags else "ShellMITC4"
    for a in flags:
        if a.startswith("--elem="):
            elem_shell = a.split("=", 1)[1]
    flexion_hk = "--flexion=hekatan" in flags
    nmodos = 0
    for a in flags:
        if a.startswith("--modos="):
            nmodos = int(a.split("=", 1)[1])

    L = []
    w = L.append
    nbar = sum(1 for e in D["elements"] if len(e) == 2)
    nsh = sum(1 for e in D["elements"] if len(e) == 4)
    w("#title " + titulo)
    w("## Modelo")
    w("# %d nudos, **%d barras** (ElasticTimoshenkoBeam) y **%d cáscaras** (%s), cargas nodales de Hekatan Struct con el peso propio incluido." % (len(nodes), nbar, nsh, elem_shell))
    w("# El mismo guion corre en *Hekatan OpenSees* y en el OpenSees oficial: lo propio de Hekatan va en líneas con `#`.")
    w("wipe")
    w("model basic -ndm 3 -ndf 6")
    for i, (x, y, z) in enumerate(nodes):
        w("node %d %s %s %s" % (i + 1, f(x), f(y), f(z)))
    for k, v in ni["supports"].items():
        w("fix %d %s" % (int(k) + 1, " ".join("1" if b else "0" for b in v)))

    secs = {}
    for idx, el in enumerate(D["elements"]):
        E = g("elasticities", idx)
        nu = g("poissonsRatios", idx, 0.3)
        rho = g("densities", idx, 0.0)
        if len(el) == 2:
            n1, n2 = el
            A = g("areas", idx); Iy = g("momentsOfInertiaY", idx); Iz = g("momentsOfInertiaZ", idx); J = g("torsionalConstants", idx)
            Avy = g("shearAreasZ", idx) or 5.0 / 6.0 * A
            Avz = g("shearAreasY", idx) or 5.0 / 6.0 * A
            Gm = g("shearModuli", idx) or E / (2 * (1 + nu))
            v = vecxz(nodes, n1, n2)
            w("geomTransf Linear %d %s %s %s" % (idx + 1, f(v[0]), f(v[1]), f(v[2])))
            w("element ElasticTimoshenkoBeam %d %d %d %s %s %s %s %s %s %s %s %d -mass %s" %
              (idx + 1, n1 + 1, n2 + 1, f(E), f(Gm), f(A), f(J), f(Iy), f(Iz), f(Avz), f(Avy), idx + 1, f(rho * A)))
        elif len(el) == 4:
            t = g("thicknesses", idx); fm = g("membraneModifiers", idx, 1.0)
            ep = max(float(g("bendingModifiers", idx, 1.0)), 1e-9) if flexion_hk else 1.0
            key = (round(E * fm, 6), round(nu, 6), round(t, 9), round(rho, 6), ep)
            if key not in secs:
                sid = 1000 + len(secs)
                w("section ElasticMembranePlateSection %d %s %s %s %s %s" % (sid, f(E * fm), f(nu), f(t), f(rho), f(ep)))
                secs[key] = sid
            w("element %s %d %s %d" % (elem_shell, idx + 1, " ".join(str(n + 1) for n in el), secs[key]))

    w("timeSeries Linear 1")
    w("pattern Plain 1 1 {")
    for k, v in ni["loads"].items():
        w("    load %d %s" % (int(k) + 1, " ".join(f(c) for c in v)))
    w("}")
    w("#hide")
    w("system BandGeneral")
    w("numberer RCM")
    w("constraints Transformation")
    w("integrator LoadControl 1.0")
    w("algorithm Linear")
    w("analysis Static")
    w("analyze 1")
    w("reactions")
    if nmodos:
        # modos de vibración: los vectores propios de OpenSees (traslaciones de cada nudo, normalizados a máximo 1) para la animación
        w("wipeAnalysis")
        w("set nmodos %d" % nmodos)
        w("set lam [eigen $nmodos]")
        w("set nnod %d" % len(nodes))
        w("""for {set m 1} {$m <= $nmodos} {incr m} {
    set l [lindex $lam [expr {$m-1}]]
    set T [expr {6.283185307179586/sqrt($l)}]
    set v {}
    set mx 0.0
    for {set n 1} {$n <= $nnod} {incr n} {
        foreach d {1 2 3} {
            set x [nodeEigenvector $n $m $d]
            lappend v $x
            if {abs($x) > $mx} { set mx [expr {abs($x)}] }
        }
    }
    set vn {}
    foreach x $v { lappend vn [format %.4g [expr {$x/$mx}]] }
    puts "HKMODO $m $T | $vn"
    puts "HEKATAN:T${m}_s=$T"
}""".replace("\r", ""))
    w("#show")
    sup = [int(k) + 1 for k in ni["supports"]]
    w("set sumRz 0.0")
    w("foreach n {%s} { set sumRz [expr {$sumRz + [lindex [nodeReaction $n] 2]}] }" % " ".join(map(str, sup)))
    # nudo más alto y nudo de mayor flecha: valores para corroborar
    zmax = max(range(len(nodes)), key=lambda i: nodes[i][2]) + 1
    w("puts \"HEKATAN:sumRz_kN=$sumRz\"")
    w("puts \"HEKATAN:uz_cumbrera_mm=[expr {[nodeDisp %d 3]*1000}]\"" % zmax)
    w("puts \"HEKATAN:ux_cumbrera_mm=[expr {[nodeDisp %d 1]*1000}]\"" % zmax)
    w("puts \"HEKATAN:uy_cumbrera_mm=[expr {[nodeDisp %d 2]*1000}]\"" % zmax)
    if not nmodos:
        w("## Deformada 3D (gírala con el ratón)")
        w("#plot")
    if nmodos:
        w("## Modos de vibración animados")
        w("# Los **%d primeros modos** del galpón: elige el modo, dale a *Reproducir* y gira la estructura con el ratón. El color es el tamaño del movimiento de cada nudo." % nmodos)
        w("#modos")
        w("#fig Modos de vibración · movimiento ×%s · color = |movimiento| normalizado" % "40")
    w("## Dibujo 3D: barras y áreas (con el cursor, DXF y DWG)")
    w("# Planta, Frente, Lateral e Iso; gira con el ratón; **Guardar DWG** lo lleva a AutoCAD.")
    w("#dibujar")
    w("# modelo")
    w("#enddibujar")
    w("## Resultados")
    w("#values")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("escrito", out, "| nudos", len(nodes), "barras", nbar, "cáscaras", nsh, "| nudo de cumbrera", zmax)


if __name__ == "__main__":
    main()
