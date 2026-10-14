# -*- coding: utf-8 -*-
"""Muro de Manabí: tiempo-historia LINEAL con interacción suelo-estructura (la que hizo Hekatan Struct) como guion OpenSees Tcl.

    python muro_th_a_tcl.py dump_0.json spec_0.json salida.tcl

dump_0.json / spec_0.json los saca  `node hekatan-struct-casos/cli/muro_manabi_th_dump.mjs 0 <carpeta>`:  la MISMA malla (224 Q4 de membrana,
nudo de la coronación, muelles de Winkler del suelo, masa del hormigón + tierra sobre el talón) y el MISMO registro (APO1 N-S, 5-40 s).
La interacción suelo-estructura es la rigidez de esos muelles: se barre ×4, ×1, ×0.25, ×0.05 y la base fija.
El tiempo-historia es un bucle de Tcl  (analyze 1 dt  paso a paso, Newmark ¼-½ de OpenSees, Rayleigh ξ = 5 % en los modos 1 y 2)."""
import json, sys


def main():
    dump, spec, out = sys.argv[1:4]
    D = json.load(open(dump, encoding="utf-8"))
    S = json.load(open(spec, encoding="utf-8"))
    nodes, els, ni, ei = D["nodes"], D["elements"], D["nodeInputs"], D["elementInputs"]
    E = ei["elasticities"]["0"]; nu = ei["poissonsRatios"]["0"]; rho = ei["densities"]["0"]; th = ei["thicknesses"]["0"]
    # membrana de Struct = tension plana con E' = E/(1-nu^2), nu' = nu/(1-nu)  (deformacion plana del muro de 1 m de fondo)
    xz = " ".join("%d %s %s" % (i + 1, repr(float(n[0])), repr(float(n[2]))) for i, n in enumerate(nodes))
    quads = " ".join(" ".join(str(k + 1) for k in e) for e in els)
    masas = " ".join("%d %s" % (int(k) + 1, repr(float(v))) for k, v in ni["masses"].items())
    sp = ni["springs"]
    resortes = " ".join("%d %d %s" % (s["node"] + 1, 1 if s["dof"] == 0 else 2, repr(float(s["k"]))) for s in sp)
    base = sorted({s["node"] + 1 for s in sp if s["dof"] == 2})      # nudos de la base: los que llevan muelle vertical
    a = " ".join("%.6g" % v for v in S["a"])
    corona = D["nudoCoronacion"] + 1
    W = []
    w = W.append
    if "patron" in S:
        w("#title Muro de Manabí: interacción suelo-estructura con funciones de impedancia (NEHRP)")
        w("## Qué se calcula")
        w("# El mismo muro de Manabí (%d nudos, %d Q4), pero con el suelo según el **NEHRP / NIST GCR 12-917-21**: Vs de los SPT del estudio, rigideces de la zapata de **Pais y Kausel** con factor de empotramiento, y reparto en los %d muelles de la base y la cara enterrada." % (len(nodes), len(els), len(sp)))
        w("# El **amortiguamiento por radiación** (β de la Tabla 2-3a, tope 25 %%) más el 5 %% de la estructura da ξ = %.2f %%; se aplica como Rayleigh en los modos 1 y 2. Se suma el **empuje dinámico del relleno** (Mononobe-Okabe) como patrón de fuerzas en la cara enterrada." % (100 * S["xi"]))
        w("# Entrada: registro **APO1 N-S de Portoviejo**, 5-40 s. Es lo que hizo *Hekatan Struct* (que a su vez coincide con SAP2000 a 1e-6 %); aquí se resuelve con OpenSees.")
    else:
        w("#title Muro de Manabí: tiempo-historia con interacción suelo-estructura")
        w("## Qué se calcula")
        w("# El muro de contención de Manabí (%d nudos, %d Q4 de membrana) sobre **muelles de Winkler** que representan al suelo: en la base `ks` (estudio de suelos, 6.59 kg/cm³) y en la cara enterrada `nh` de Terzaghi." % (len(nodes), len(els)))
        w("# La entrada es el registro **APO1 N-S de Portoviejo** (16-abr-2016), de 5 a 40 s, aplicado en la base. La respuesta es **relativa** al terreno y el amortiguamiento es **Rayleigh con ξ = 5 %** en los modos 1 y 2.")
        w("# Se repite el cálculo con el suelo **×4, ×1, ×0.25 y ×0.05** y con la **base fija**: así se ve cómo el suelo alarga el periodo y cambia el cortante en la base. Es lo que hizo *Hekatan Struct*.")
    w("#hide")
    w("set E %s; set nu %s; set rho %s; set esp %s" % (repr(E), repr(nu), repr(rho), repr(th)))
    w("set xz {%s}" % xz)
    w("set quads {%s}" % quads)
    w("set masas {%s}" % masas)
    w("set resortes {%s}" % resortes)
    w("set base {%s}" % " ".join(map(str, base)))
    w("set corona %d" % corona)
    w("set dt %r" % S["dt"])
    w("set acel {%s}" % a)
    ise = "patron" in S                       # spec NEHRP: amortiguamiento modal de radiación + empuje dinámico de M-O
    w("set xi %r" % (S["xi"] if ise else 0.05))
    w("set ise %d" % (1 if ise else 0))
    if ise:
        w("set patron {%s}" % " ".join("%d %s %s" % (int(n) + 1, repr(f[0]), repr(f[2])) for n, f in S["patron"].items()))
        w("set a2 {%s}" % " ".join("%.6g" % v for v in S["a2"]))
    w("""
# ---- el muro con la rigidez del suelo multiplicada por fk (fk < 0 = base fija) ----
proc montar {fk} {
    global E nu rho esp xz quads masas resortes base ex
    set ex {}
    wipe
    model basic -ndm 2 -ndf 2
    foreach {n x y} $xz { node $n $x $y }
    nDMaterial ElasticIsotropic 1 $E $nu $rho
    nDMaterial PlaneStress 2 1
    set e 0
    foreach {a b c d} $quads { element quad [incr e] $a $b $c $d $esp PlaneStress 2 }
    foreach {n m} $masas { mass $n $m $m }
    if {$fk < 0} {
        foreach n $base { fix $n 1 1 }
    } else {
        set id 0
        foreach {n dir k} $resortes {
            incr id
            node [expr {100000+$id}] [nodeCoord $n 1] [nodeCoord $n 2]
            fix [expr {100000+$id}] 1 1
            uniaxialMaterial Elastic [expr {1000+$id}] [expr {$k*$fk}]
            element zeroLength [expr {50000+$id}] [expr {100000+$id}] $n -mat [expr {1000+$id}] -dir $dir
            if {$dir == 1} { lappend ex [expr {50000+$id}] }
        }
    }
}
# ---- un cálculo completo: modos, Rayleigh y el tiempo-historia entero dentro de OpenSees; devuelve  T1  ux_corona(mm)  V_base(kN/m)  serie ----
proc th {fk} {
    global acel dt xi corona resortes ex ise patron a2
    montar $fk
    set lam [eigen 2]
    set w1 [expr {sqrt([lindex $lam 0])}]
    set w2 [expr {sqrt([lindex $lam 1])}]
    # con ISE xi = beta de radiación (NEHRP, tope 25 %) + 5 % de la estructura; Rayleigh en los modos 1-2 (modalDamping de OpenSees no converge con el nº de modos)
    set aM [expr {2.0*$xi*$w1*$w2/($w1+$w2)}]
    set aK [expr {2.0*$xi/($w1+$w2)}]
    rayleigh $aM 0.0 $aK 0.0
    timeSeries Path 1 -dt $dt -values $acel
    pattern UniformExcitation 1 1 -accel 1
    if {$ise} {
        # empuje dinámico del relleno (Mononobe-Okabe): patrón unitario x a(t)/(kh g)
        timeSeries Path 2 -dt $dt -values $a2
        pattern Plain 2 2 {
            foreach {n fx fy} $patron { load $n $fx $fy }
        }
    }
    # los resultados se graban con recorders (en C++) y se leen UNA vez: sin un nodeDisp de Tcl por paso
    set fu [file tempfile fnu]; close $fu
    recorder Node -file $fnu -node $corona -dof 1 disp
    if {$fk >= 0 && [llength $ex] > 0} {
        set ff [file tempfile fnf]; close $ff
        recorder Element -file $fnf -ele {*}$ex force
    }
    wipeAnalysis
    constraints Plain
    numberer RCM
    system BandGeneral
    test NormDispIncr 1.0e-10 10 0
    # lineal y dt constante: la matriz se factoriza UNA vez (con -factorOnce 4 veces mas rapido, mismo resultado)
    algorithm Linear -factorOnce
    integrator Newmark 0.5 0.25
    analysis Transient
    set n [expr {[llength $acel] - 1}]
    # TODOS los pasos en una sola orden: el bucle corre dentro de OpenSees
    if {[analyze $n $dt] != 0} { puts "no converge" }
    remove recorders
    set ser {}
    set umax 0.0
    set fh [open $fnu r]
    foreach u [split [string trim [read $fh]] "\n"] {
        lappend ser [format %.4f [expr {1000.0*$u}]]
        if {abs($u) > $umax} { set umax [expr {abs($u)}] }
    }
    close $fh
    file delete $fnu
    set vmax 0.0
    if {$fk >= 0 && [llength $ex] > 0} {
        set fh [open $fnf r]
        foreach row [split [string trim [read $fh]] "\n"] {
            # force de zeroLength = [fx_i fy_i fx_j fy_j]: el nudo i es la tierra, el j es el muro (la fuerza sobre el muro es la 3.ª columna de cada 4)
            set V 0.0
            set i 0
            foreach f $row { if {$i % 4 == 2} { set V [expr {$V + $f}] }; incr i }
            if {abs($V) > $vmax} { set vmax [expr {abs($V)}] }
        }
        close $fh
        file delete $fnf
    }
    return [list [expr {6.283185307179586/$w1}] [expr {1000.0*$umax}] $vmax $ser]
}
""".replace("\r", ""))
    w("set W 138.60")
    w(r"""set lista {fija -1 s4 4.0 s1 1.0 s025 0.25 s005 0.05}
if {$ise} { set lista {ise 1.0} }
foreach {nombre fk} $lista {
    lassign [th $fk] T1 ux V ser
    if {$nombre in {fija s1 s025 ise}} { puts "HEKATAN:ux_${nombre}_t=\[[join $ser ,]\]" }
    puts "HEKATAN:T1_${nombre}_s=$T1"
    puts "HEKATAN:ux_${nombre}_mm=$ux"
    if {$fk >= 0} { puts "HEKATAN:V_${nombre}_kNm=$V"; puts "HEKATAN:VW_${nombre}=[expr {$V/$W}]" }
}""")
    w("#show")
    if "patron" in S:
        w("## Resultados")
        w("# Periodo T1, desplazamiento máximo de la coronación y cortante máximo en la base (V/W con W = 138.6 kN/m). *Hekatan Struct* (modal, 12 modos): T1 0.0861 s, u = 3.148 mm, V = 81.99 kN/m.")
        w("## Desplazamiento de la coronación en el tiempo")
        w("# Con el suelo de impedancias y el empuje del relleno, la coronación se mueve unos 3 mm como máximo.")
        w("#gfx")
        w("# figure(); var t=[]; for(var i=0;i<ux_ise_t.length;i++) t.push((i+1)*%r);" % S["dt"])
        w("# plot(t, ux_ise_t, 'r-');")
        w("# title('Coronación del muro, APO1 N-S, ISE NEHRP'); xlabel('t [s]'); ylabel('u_x [mm]'); grid('on');")
        w("#endgfx")
    else:
        w("## Resultados")
        w("# Para cada rigidez del suelo: periodo T1, desplazamiento máximo de la coronación y cortante máximo en la base (V/W con W = 138.6 kN/m).")
        w("## Desplazamiento de la coronación en el tiempo")
        w("# Con el suelo, el muro se mueve más y más despacio: la curva roja (suelo del estudio) y la verde (suelo blando) contra la azul (base fija).")
        w("#gfx")
        w("# figure(); var t=[]; for(var i=0;i<ux_s1_t.length;i++) t.push((i+1)*%r);" % S["dt"])
        w("# plot(t, ux_fija_t, 'b-'); hold('on'); plot(t, ux_s1_t, 'r-'); plot(t, ux_s025_t, 'g-');")
        w("# title('Coronación del muro, APO1 N-S'); xlabel('t [s]'); ylabel('u_x [mm]'); grid('on'); legend('base fija', 'suelo x1', 'suelo x0.25');")
        w("#endgfx")
    w("#values")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(W) + "\n")
    print("escrito", out, "| nudos", len(nodes), "Q4", len(els), "| muelles", len(sp), "| base", len(base), "| pasos", len(S["a"]))


if __name__ == "__main__":
    main()
