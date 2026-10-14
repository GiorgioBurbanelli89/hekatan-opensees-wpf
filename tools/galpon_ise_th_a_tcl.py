# -*- coding: utf-8 -*-
"""Ejemplo 14: galpón curvo con interacción suelo-estructura (impedancias NIST) y TIEMPO-HISTORIA en Hekatan OpenSees.

    python galpon_ise_th_a_tcl.py "12 - Galpon curvo modos animados.tcl" spec_0.json salida.tcl

Toma el modelo del ejemplo 12 (214 nudos, 443 barras, 100 cáscaras), quita los 12 empotramientos y pone bajo cada columna una zapata rígida
con los 6 muelles de las funciones de impedancia (ise_lib.tcl, NIST GCR 12-917-21, Pais y Kausel). Registro: APO1 N-S 5-40 s (el de Struct)."""
import json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    src, spec, out = sys.argv[1:4]
    L = open(src, encoding="utf-8", errors="replace").read().replace("\r", "").split("\n")
    S = json.load(open(spec, encoding="utf-8"))
    fin = next(i for i, l in enumerate(L) if l.startswith("timeSeries Linear 1"))
    modelo = [l for l in L[:fin] if l and not l.startswith("#")]
    nodos = {}
    for l in modelo:
        m = re.match(r"node (\d+) (\S+) (\S+) (\S+)$", l)
        if m: nodos[int(m.group(1))] = tuple(float(m.group(k)) for k in (2, 3, 4))
    base = [int(l.split()[1]) for l in modelo if l.startswith("fix ")]
    modelo = [l for l in modelo if not l.startswith("fix ")]
    lib = open(os.path.join(AQUI, "ise_lib.tcl"), encoding="utf-8").read()
    a = " ".join("%.6g" % v for v in S["a"])
    W = []
    w = W.append
    w("#title Galpón curvo: interacción suelo-estructura (impedancias) y tiempo-historia")
    w("## Qué se calcula")
    w("# El galpón curvo del ejemplo 12 (214 nudos, 443 barras, 100 cáscaras) con el **suelo** bajo las 12 columnas: cada una apoya en una **zapata rígida** de 2 × 2 m, empotrada 0.6 m, con los 6 muelles de las *funciones de impedancia* del **NIST GCR 12-917-21** (Pais y Kausel).")
    w("# Suelo supuesto (no hay estudio del galpón): el del estudio de Manabí, G = 38 666 kPa (Vs ≈ 206 m/s ya reducido por deformación), ν = 0.3. Se compara **base fija**, **suelo ×1** y **suelo ×0.25** (blando).")
    w("# Entrada: **APO1 N-S de Portoviejo** (16-abr-2016), 5-40 s, en la dirección **X** y en la **Y**; Newmark ¼-½ y Rayleigh ξ = 5 % en los modos 1 y 2. La radiación se desprecia: con zapatas de 2 m y T ≈ 0.3 s el amortiguamiento por radiación es mínimo.")
    w("#hide")
    w(lib)
    w("set G0 38665.58988331968; set nuS 0.3; set Bz 1.0; set Lz 1.0; set Dz 0.6")
    w("set base {%s}" % " ".join("%d %s %s" % (n, repr(nodos[n][0]), repr(nodos[n][1])) for n in base))
    w("set dt %r" % S["dt"])
    w("set acel {%s}" % a)
    w("set xi 0.05")
    w("proc montar {fk} {\n    global G0 nuS Bz Lz Dz base")
    w("\n".join("    " + l for l in modelo))
    w("""    set i 0
    if {$fk < 0} {
        foreach {n x y} $base { fix $n 1 1 1 1 1 1 }
    } else {
        set K [ise_K [expr {$G0*$fk}] $nuS $Bz $Lz $Dz]
        foreach {n x y} $base {
            incr i
            ise_cimentacion [expr {1000+$i}] $x $y [expr {-$Dz}] $K [list $n] [expr {2000+$i}]
        }
    }
}""")
    w(r"""
# un cálculo completo: modos, Rayleigh y tiempo-historia en la dirección dir (1 = X, 2 = Y); devuelve T1 T2 T3 ux_corona(mm) V_base(kN) serie
proc th {fk dir} {
    global acel dt xi base
    wipe
    model basic -ndm 3 -ndf 6
    montar $fk
    set lam [eigen 3]
    set w1 [expr {sqrt([lindex $lam 0])}]
    set w2 [expr {sqrt([lindex $lam 1])}]
    set T {}
    foreach l $lam { lappend T [expr {6.283185307179586/sqrt($l)}] }
    set aM [expr {2.0*$xi*$w1*$w2/($w1+$w2)}]
    set aK [expr {2.0*$xi/($w1+$w2)}]
    rayleigh $aM 0.0 $aK 0.0
    timeSeries Path 1 -dt $dt -values $acel
    pattern UniformExcitation 1 $dir -accel 1
    set fu [file tempfile fnu]; close $fu
    recorder Node -file $fnu -node 6 -dof $dir disp
    set fr [file tempfile fnr]; close $fr
    set nr {}
    if {$fk < 0} { foreach {n x y} $base { lappend nr $n } } else { set i 0; foreach {n x y} $base { incr i; lappend nr [expr {2000+$i}] } }
    recorder Node -file $fnr -node {*}$nr -dof $dir reaction
    wipeAnalysis
    constraints Transformation
    numberer RCM
    system BandGeneral
    test NormDispIncr 1.0e-10 10 0
    algorithm Linear -factorOnce
    integrator Newmark 0.5 0.25
    analysis Transient
    if {[analyze [expr {[llength $acel]-1}] $dt] != 0} { puts "no converge" }
    remove recorders
    set ser {}; set umax 0.0
    set fh [open $fnu r]
    foreach u [split [string trim [read $fh]] "\n"] { lappend ser [format %.4f [expr {1000.0*$u}]]; if {abs($u) > $umax} { set umax [expr {abs($u)}] } }
    close $fh; file delete $fnu
    set vmax 0.0
    set fh [open $fnr r]
    foreach row [split [string trim [read $fh]] "\n"] { set V 0.0; foreach f $row { set V [expr {$V+$f}] }; if {abs($V) > $vmax} { set vmax [expr {abs($V)}] } }
    close $fh; file delete $fnr
    return [list {*}$T [expr {1000.0*$umax}] $vmax $ser]
}
foreach {nombre fk} {fija -1 s1 1.0 s025 0.25} {
    foreach {dn dir} {X 1 Y 2} {
        lassign [th $fk $dir] T1 T2 T3 u V ser
        if {$nombre in {fija s1}} { puts "HEKATAN:u${dn}_${nombre}_t=\[[join $ser ,]\]" }
        if {$dir == 1} { puts "HEKATAN:T1_${nombre}_s=$T1"; puts "HEKATAN:T2_${nombre}_s=$T2"; puts "HEKATAN:T3_${nombre}_s=$T3" }
        puts "HEKATAN:u${dn}_${nombre}_mm=$u"
        puts "HEKATAN:V${dn}_${nombre}_kN=$V"
    }
}""")
    w("#show")
    w("## Resultados")
    w("# Periodos T1-T3, desplazamiento máximo de la cumbrera (nudo 6) y cortante máximo en la base (suma de las reacciones en la dirección del sismo), para base fija, suelo ×1 y suelo ×0.25.")
    w("## Desplazamiento de la cumbrera en el tiempo")
    w("# Con el suelo del estudio el galpón se alarga de periodo y se mueve algo más que con la base fija.")
    w("#gfx")
    w("# figure(); var t=[]; for(var i=0;i<uY_s1_t.length;i++) t.push((i+1)*%r);" % S["dt"])
    w("# plot(t, uY_fija_t, 'b-'); hold('on'); plot(t, uY_s1_t, 'r-');")
    w("# title('Cumbrera del galpón, APO1 N-S en Y'); xlabel('t [s]'); ylabel('u_y [mm]'); grid('on'); legend('base fija', 'suelo x1');")
    w("#endgfx")
    w("#values")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(W) + "\n")
    print("escrito", out, "| nudos", len(nodos), "| bases", len(base), "| pasos", len(S["a"]))


if __name__ == "__main__":
    main()
