# -*- coding: utf-8 -*-
"""Muro de contención de Manabí con sismo (el de Hekatan Lab, ejemplo 26) como guion OpenSees Tcl con la GRIETA animada.

    python muro_manabi_a_tcl.py salida.tcl [nsteps=40] [smax=1.4]

Misma malla (776 Q4), mismas cargas (PP + relleno + empuje de Coulomb + sismo de Mononobe-Okabe + inercia kh·PP) y mismos muelles de la
base que muro_manabi_grieta_animada.m. El hormigón sin acero es ASDConcrete3D (daño a tracción, curva de Abaqus escalada a ft = 1.5 MPa)
dentro de un PlaneStrain. El sismo sube s = 0 → smax (s = 1 es el kh de la NEC); cada paso = un cuadro de la animación."""
import math, sys


def main():
    out = sys.argv[1]
    nsteps = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    du = float(sys.argv[4]) if len(sys.argv) > 4 else -0.0001
    smax = float(sys.argv[3]) if len(sys.argv) > 3 else 1.4
    Hf, tf, tTop, tBase, toe, heel, L = 2.6, 0.4, 0.25, 0.40, 0.70, 1.90, 1.0
    E, nu, gc, gs = 4700 * math.sqrt(21) * 1000, 0.2, 23.0, 18.5
    phi, dl, kh = 30.0, 20.0, 0.336
    ks = 6.59 * 9806.65
    ft = 1500.0
    f, d, psi = math.radians(phi), math.radians(dl), math.atan(kh)
    Ka = math.cos(f) ** 2 / (math.cos(d) * (1 + math.sqrt(math.sin(f + d) * math.sin(f) / math.cos(d))) ** 2)
    Kae = math.cos(f - psi) ** 2 / (math.cos(psi) * math.cos(d + psi) * (1 + math.sqrt(math.sin(f + d) * math.sin(f - psi) / math.cos(d + psi))) ** 2)
    xb = toe + tBase
    xs = [0.05 * i for i in range(int(round(toe / 0.05)))] + [toe + tBase * k / 6 for k in range(7)] + [xb + 0.05 * i for i in range(1, 39)]
    ncf, nrf, nrs = len(xs), 8, 52
    NF = (nrf + 1) * ncf
    NN = NF + nrs * 7
    XY = [None] * (NN + 1)                                    # 1-based como en el .m
    for r in range(nrf + 1):
        for c in range(1, ncf + 1):
            XY[r * ncf + c] = (xs[c - 1], tf * r / nrf)
    for k in range(1, nrs + 1):
        z = tf + Hf * k / nrs
        xf = toe + (tBase - tTop) * (z - tf) / Hf
        for m in range(7):
            XY[NF + (k - 1) * 7 + m + 1] = (xf + (xb - xf) * m / 6, z)
    els = []
    for r in range(nrf):
        for c in range(1, ncf):
            els.append((r * ncf + c, r * ncf + c + 1, (r + 1) * ncf + c + 1, (r + 1) * ncf + c))
    for k in range(1, nrs + 1):
        for m in range(6):
            a = nrf * ncf + 15 + m if k == 1 else NF + (k - 2) * 7 + m + 1
            els.append((a, a + 1, NF + (k - 1) * 7 + m + 2, NF + (k - 1) * 7 + m + 1))

    def area(e):
        p = [XY[n] for n in e]
        return 0.5 * abs(sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1] for i in range(4)))

    Fs, Fq = {}, {}

    def add(F, n, c, v):
        F[(n, c)] = F.get((n, c), 0.0) + v
    for e in els:
        V = area(e) * L
        for n in e:
            add(Fs, n, 1, -gc * V / 4)
            add(Fq, n, 0, -kh * gc * V / 4)
    for c in range(21, ncf + 1):
        w = (xs[c - 1] - xs[c - 2]) / 2 if c == ncf else (xs[c] - xs[c - 2]) / 2
        add(Fs, nrf * ncf + c, 1, -gs * Hf * w * L)
    dz = Hf / nrs
    for k in range(nrs + 1):
        n = nrf * ncf + 21 if k == 0 else NF + (k - 1) * 7 + 7
        zd = Hf - Hf * k / nrs
        l = dz / 2 if k in (0, nrs) else dz
        p, dp = Ka * gs * zd, (Kae - Ka) * gs * (Hf - zd)
        add(Fs, n, 0, -p * math.cos(d) * l * L)
        add(Fs, n, 1, -p * math.sin(d) * l * L)
        add(Fq, n, 0, -dp * math.cos(d) * l * L)
        add(Fq, n, 1, -dp * math.sin(d) * l * L)

    def lst(F):
        nodos = sorted({n for n, _ in F})
        o = []
        for n in nodos:
            o += [str(n), repr(F.get((n, 0), 0.0)), repr(F.get((n, 1), 0.0))]
        return " ".join(o)

    # ablandamiento a tracción: curva de Abaqus escalada a ft (cx, cs del .m); daño secante d = 1 − σ/(E·ε)
    cx = [ft / E, 0.0006, 0.002, 0.006]
    cs = [ft * v for v in (1.0, 0.19, 0.038, 0.019)]
    Te = [0.0] + cx
    Ts = [0.0] + cs
    Td = [0.0] + [min(0.995, max(0.0, 1.0 - s / (E * e))) for e, s in zip(cx, cs)]
    fcu = 21000.0
    Ce = [0.0, 0.0006 * 0 + fcu * 0.4 / E, 0.002, 0.004]
    Cs = [0.0, fcu * 0.4, fcu, 0.8 * fcu]
    Cd = [0.0, 0.0, 1.0 - fcu / (E * 0.002), 1.0 - 0.8 * fcu / (E * 0.004)]

    W = []
    w = W.append
    w("#title Muro de contención de Manabí con sismo: la grieta crece paso a paso")
    w("## Qué se calcula")
    w("# El mismo muro del ejemplo 26 de Hekatan Lab: fuste de 2.60 m (coronación 0.25 m, pie 0.40 m), zapata de 0.40 m, puntera 0.70 m y talón 1.90 m, en **deformación plana** con %d elementos Q4." % len(els))
    w("# Cargas: peso propio, relleno sobre el talón, empuje de Coulomb y **sismo de Mononobe-Okabe** más la inercia *kh·PP* con kh = %.3f (NEC). Apoyo: muelles de balasto en la base." % kh)
    w("# El hormigón es **ASDConcrete3D** (daño a tracción) sin acero, con f_t = 1.5 MPa. El sismo sube de s = 0 a s = %.1f (s = 1 es el kh de la NEC); cada paso es un cuadro." % smax)
    w("#hide")
    w("wipe")
    w("model basic -ndm 2 -ndf 2")
    w("set E %r" % E)
    w("set nxy %d" % NN)
    w("set xy {%s}" % " ".join("%d %s %s" % (i, repr(XY[i][0]), repr(XY[i][1])) for i in range(1, NN + 1)))
    w("foreach {n x y} $xy { node $n $x $y }")
    w("nDMaterial ASDConcrete3D 1 $E %r -Te %s -Ts %s -Td %s -Ce %s -Cs %s -Cd %s -rho 0.0 -eta 0.0 -Kc 0.6667 -cdf 0.0" % (
        nu, " ".join(repr(x) for x in Te), " ".join(repr(x) for x in Ts), " ".join(repr(x) for x in Td),
        " ".join(repr(x) for x in Ce), " ".join(repr(x) for x in Cs), " ".join(repr(x) for x in Cd)))
    w("nDMaterial PlaneStrain 2 1")
    w("set quads {%s}" % " ".join(" ".join(map(str, e)) for e in els))
    w("set e 0")
    w("foreach {a b c d} $quads { element quad [incr e] $a $b $c $d 1.0 PlaneStrain 2 }")
    w("set nel $e")
    # muelles de la base (fila 0): vertical ks·A, horizontal 0.5·ks·A, con un nudo de tierra por columna
    w("uniaxialMaterial Elastic 11 1.0")
    for c in range(1, ncf + 1):
        wv = (xs[1] - xs[0]) / 2 if c == 1 else ((xs[c - 1] - xs[c - 2]) / 2 if c == ncf else (xs[c] - xs[c - 2]) / 2)
        w("node %d %s 0.0; fix %d 1 1" % (10000 + c, repr(xs[c - 1]), 10000 + c))
        w("uniaxialMaterial Elastic %d %s; uniaxialMaterial Elastic %d %s" % (100 + 2 * c, repr(0.5 * ks * wv * L), 101 + 2 * c, repr(ks * wv * L)))
        w("element zeroLength %d %d %d -mat %d %d -dir 1 2" % (5000 + c, 10000 + c, c, 100 + 2 * c, 101 + 2 * c))
    w("set Fs {%s}" % lst(Fs))
    w("set Fq {%s}" % lst(Fq))
    # el tiempo t es el factor de carga: de 0 a 1 sube lo estático (PP + relleno + Coulomb); de 1 en adelante sube el sismo s = t - 1
    w("timeSeries Path 1 -time {0.0 1.0 100.0} -values {0.0 1.0 1.0}")
    w("pattern Plain 1 1 { foreach {n fx fy} $Fs { load $n $fx $fy } }")
    w("timeSeries Path 2 -time {0.0 1.0 100.0} -values {0.0 0.0 99.0}")
    w("pattern Plain 2 2 { foreach {n fx fy} $Fq { load $n $fx $fy } }")
    w("system BandGeneral; numberer RCM; constraints Plain; test NormDispIncr 1.0e-6 100 0; algorithm KrylovNewton; analysis Static")
    w("# ---- 1) estática: peso propio, relleno y empuje de Coulomb (el sismo todavía en cero) ----")
    w("integrator LoadControl 0.2")
    w("set ok [analyze 5]")
    w("# ---- 2) el sismo sube s = 0 .. %s; cada paso imprime un cuadro  HKFRAME s | u | d  (d = daño a tracción de cada elemento) ----" % smax)
    w("set nsteps %d" % nsteps)
    w("set tip %d" % (NF + nrs * 7 - 6))
    w("set du %r" % du)
    w("set smax %r" % smax)
    w("""proc cuadro {s} {
    global nxy nel tip
    set u {}
    for {set n 1} {$n <= $nxy} {incr n} { lappend u [format %.4g [nodeDisp $n 1]] [format %.4g [nodeDisp $n 2]] }
    set dm {}
    for {set e 1} {$e <= $nel} {incr e} { lappend dm [format %.3g [lindex [eleResponse $e material 1 damage] 0]] }
    puts "HKFRAME $s [format %.2f [expr {[nodeDisp $tip 1]*1000}]] | $u | $dm"
}
# el sismo se sube por DESPLAZAMIENTO de la coronacion (el ablandamiento deja atras el pico de carga: con control de carga no pasa de ahi)
integrator DisplacementControl $tip 1 $du
cuadro 0.0
set sfinal 0.0
set fallo 0
set k 0
while {$sfinal < $smax && $k < $nsteps && !$fallo} {
    incr k
    set bien 0
    # si el paso no converge (la grieta se localiza) se prueba más fino y luego más grueso: el ablandamiento no es monótono en el paso
    foreach m {1.0 0.05 4.0 10.0 25.0} {
        integrator DisplacementControl $tip 1 [expr {$du*$m}]
        if {[analyze 1] == 0} { set bien 1; break }
    }
    integrator DisplacementControl $tip 1 $du
    if {!$bien} { set fallo 1; break }
    set sfinal [expr {[getTime] - 1.0}]
    cuadro [format %.4f $sfinal]
}""")
    w("#show")
    w('puts "HEKATAN:s_final=$sfinal"')
    w('puts "HEKATAN:cuadros=[expr {$fallo ? $k : $nsteps+1}]"')
    w("## La grieta, paso a paso")
    w("# Dale a **Reproducir** o arrastra el control. El color es el *daño a tracción* d (0 = sano, 1 = abierta): el hormigón sin acero falla por una sola grieta en el pie del fuste.")
    w("#grieta 40")
    w("#fig Daño a tracción en la malla deformada · deformación ×40 · jet 0 a 0.95")
    w("## Resultados")
    w("#values")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(W) + "\n")
    print("escrito (esqueleto)", out, "| Q4", len(els), "| nudos", NN, "| Td", [round(x, 3) for x in Td])


if __name__ == "__main__":
    main()
