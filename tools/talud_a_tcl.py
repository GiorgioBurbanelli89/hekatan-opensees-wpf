# -*- coding: utf-8 -*-
"""Talud de Hekatan Geotechnic (public/models/demo04.json: malla T6 de GEO5) como guion OpenSees Tcl:
cada T6 se parte en 4 triángulos de 3 nudos (tri31), suelo Drucker-Prager (el mismo cono que Geotechnic: α = 2 sinφ/(√3 (3+sinφ)),
k = 6 c cosφ/(√3 (3+sinφ))) y el factor de seguridad por REDUCCIÓN DE RESISTENCIA con un bucle de Tcl.

    python talud_a_tcl.py demo04.json salida.tcl [etapa=1]

Equivalencia medida en OpenSees (un elemento, deformación plana): f = ||s|| + ρ·I1 − √(2/3)·σy  →  ρ = √2·α,  σy = √3·k."""
import json, sys, math


def main():
    src, out = sys.argv[1], sys.argv[2]
    etapa = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    m = json.load(open(src, encoding="utf-8"))
    X, Y, ELE, EMAT, MAT, FIXED = m["X"], m["Y"], m["ELE"], m["EMAT"], m["MAT"], m["FIXED"]
    st = m["stages"][etapa - 1]

    # cargas nodales de la etapa (kN): suma de los vectores que lista la etapa
    F = [0.0] * len(m["Fg"])
    for nombre in st["loads"]:
        v = m[nombre]
        for i, x in enumerate(v):
            F[i] += x
    cargas = []
    for n in range(len(X)):
        fx, fy = F[2 * n], F[2 * n + 1]
        if abs(fx) > 1e-12 or abs(fy) > 1e-12:
            cargas += [n + 1, fx, fy]

    # cada T6 -> 4 tri31 con los 6 nudos (los nudos medios se buscan por coordenadas: el orden de GEO5 no es 12-23-31)
    def mid(e, i, j):
        """el nudo medio de la arista i-j: el de e[3:] mas cercano a su punto medio (GEO5 no lo guarda en orden fijo)."""
        px, py = (X[i] + X[j]) / 2, (Y[i] + Y[j]) / 2
        k = min(e[3:], key=lambda q: (X[q] - px) ** 2 + (Y[q] - py) ** 2)
        if (X[k] - px) ** 2 + (Y[k] - py) ** 2 > 1e-4 * ((X[i] - X[j]) ** 2 + (Y[i] - Y[j]) ** 2 + 1e-12):
            raise SystemExit("T6 sin nudo medio en %s" % (e,))
        return k
    tris = {}
    for e, mat in zip(ELE, EMAT):
        n1, n2, n3 = e[:3]
        a, b, c = mid(e, n1, n2), mid(e, n2, n3), mid(e, n3, n1)
        for t in ((n1, a, c), (a, n2, b), (c, b, n3), (a, b, c)):
            tris.setdefault(mat, []).extend(k + 1 for k in t)

    fx = {}
    for d in FIXED:
        n, c = d // 2, d % 2
        fx.setdefault(n + 1, [0, 0])[c] = 1

    W = []
    w = W.append
    w("#title Talud Demo04 de Hekatan Geotechnic en Hekatan OpenSees (%s)" % st["name"])
    w("## Qué se calcula")
    w("# El talud de **GEO5 Demo04** (%d nudos y %d elementos T6; cada T6 se parte en 4 triángulos) con suelo **Drucker-Prager**." % (len(X), len(ELE)))
    w("# El factor de seguridad sale por **reducción de resistencia (SRM)**: se divide `c` y `tan φ` entre F y se busca el F donde el cálculo deja de converger.")
    w("# GEO5 da **FS = %s** en esta etapa." % st["geo5"])
    w("#hide")
    w("set pi [expr {acos(-1.0)}]")
    w("set nsteps 200")
    w("set tol 1.0e-4")
    w("set nit 100")
    # propiedades: E nu phi c gamma psi
    for i, p in enumerate(MAT):
        w("set mat%d {%s}" % (i + 1, " ".join(repr(float(x)) for x in p)))
    w("set nmat %d" % len(MAT))
    w("set xy {%s}" % " ".join("%d %s %s" % (i + 1, repr(float(X[i])), repr(float(Y[i]))) for i in range(len(X))))
    w("set apoyos {%s}" % " ".join("%d %d %d" % (n, f[0], f[1]) for n, f in sorted(fx.items())))
    for mat, lst in sorted(tris.items()):
        w("set tris%d {%s}" % (mat, " ".join(map(str, lst))))
    w("set cargas {%s}" % " ".join(repr(x) if isinstance(x, float) else str(x) for x in cargas))
    w("""
# ---- el modelo completo para un factor de reducción F (se reconstruye en cada intento) ----
proc construir {F} {
    global mat1 mat2 xy apoyos tris1 tris2 cargas nmat pi nsteps tol nit
    wipe
    model basic -ndm 2 -ndf 2
    foreach {n x y} $xy { node $n $x $y }
    foreach {n fx fy} $apoyos { fix $n $fx $fy }
    set s3 [expr {sqrt(3.0)}]
    for {set m 1} {$m <= $nmat} {incr m} {
        lassign [set mat$m] E nu phi c gam psi
        set cf [expr {$c / $F}]
        set pf [expr {atan(tan($phi*$pi/180.0) / $F)}]
        set sn [expr {sin($pf)}]
        set al [expr {2.0*$sn/($s3*(3.0+$sn))}]
        set kk [expr {6.0*$cf*cos($pf)/($s3*(3.0+$sn))}]
        set K [expr {$E/(3.0*(1.0-2.0*$nu))}]
        set G [expr {$E/(2.0*(1.0+$nu))}]
        # Drucker-Prager de OpenSees: f = ||s|| + rho*I1 - sqrt(2/3)*sigmaY   (rho = sqrt2*alpha, sigmaY = sqrt3*k; psi = 0)
        nDMaterial DruckerPrager $m $K $G [expr {$s3*$kk}] [expr {sqrt(2.0)*$al}] 0.0 0.0 0.0 0.0 0.0 0.0 0.0 [expr {$gam/9.81}]
    }
    set e 0
    for {set m 1} {$m <= $nmat} {incr m} {
        foreach {a b c} [set tris$m] { element tri31 [incr e] $a $b $c 1.0 PlaneStrain $m }
    }
    timeSeries Linear 1
    pattern Plain 1 1 {
        foreach {n fx fy} $cargas { load $n $fx $fy }
    }
    system BandGeneral
    numberer RCM
    constraints Plain
    test NormDispIncr $tol $nit 0
    algorithm Newton
    integrator LoadControl [expr {1.0/$nsteps}]
    analysis Static
}
# 1 = el talud aguanta con la resistencia reducida entre F (las 10 cargas convergen); 0 = no
proc aguanta {F} {
    global nsteps
    construir $F
    for {set i 0} {$i < $nsteps} {incr i} { if {[analyze 1] != 0} { return 0 } }
    return 1
}
set lo 1.0
set hi 3.0
set pasos 0
while {$hi - $lo > 0.01} {
    set mid [expr {0.5*($lo+$hi)}]
    if {[aguanta $mid]} { set lo $mid } else { set hi $mid }
    incr pasos
}
set FS [expr {0.5*($lo+$hi)}]
# se deja el modelo montado con el ultimo F que aguanta, para ver su deformada
aguanta $lo
""".replace("\r", ""))
    w("#show")
    w('puts "HEKATAN:FS_SRM=$FS"')
    w('puts "HEKATAN:FS_GEO5=%s"' % st["geo5"])
    w('puts "HEKATAN:pasos_biseccion=$pasos"')
    w("## Deformada con la resistencia reducida")
    w("# Con **F = %s** (último que aguanta) el desplazamiento crece en la zona de falla." % "${lo}".replace("${lo}", "el último F estable"))
    w("#plot")
    w("## Resultados")
    w("#values")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(W) + "\n")
    print("escrito", out, "| tri31:", {k: len(v) // 3 for k, v in tris.items()}, "| apoyos", len(fx), "| cargas", len(cargas) // 3)


if __name__ == "__main__":
    main()
