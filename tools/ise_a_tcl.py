# -*- coding: utf-8 -*-
"""Ejemplo 11: interacción suelo-estructura con FUNCIONES DE IMPEDANCIA (NIST GCR 12-917-21, cap. 2) en Hekatan OpenSees.

    python ise_a_tcl.py salida.tcl

Una columna con masa en la punta sobre una zapata rígida; el suelo se representa con los 6 muelles de la zapata (Pais y Kausel 1988, Tabla 2-2a).
La comprobación: el periodo del modelo de OpenSees (eigen) contra la fórmula cerrada del NIST,
    (T~/T)^2 = 1 + k/Kx + k·h^2/Kyy       (ec. 2-?: traslación + giro de la base),  k = 3EI/h^3."""
import os, sys

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    out = sys.argv[1]
    lib = open(os.path.join(AQUI, "ise_lib.tcl"), encoding="utf-8").read()
    W = []
    w = W.append
    w("#title Interacción suelo-estructura con funciones de impedancia")
    w("## Qué se calcula")
    w("# Una **columna** de hormigón de 0.50 × 0.50 m y 4 m de alto, con una masa de 20 t en la punta, apoyada en una **zapata rígida** de 3.0 × 4.0 m sobre un suelo con velocidad de onda de corte *Vs*.")
    w("# El suelo no se dibuja: se sustituye por los **6 muelles de la zapata** (traslación en x, y, z y giro en x, y, z). Sus rigideces salen de las *funciones de impedancia* del **NIST GCR 12-917-21** (Pais y Kausel, 1988).")
    w("# Con base fija el periodo es T; con el suelo se alarga a T~. El NIST da la razón de periodos de una forma cerrada:")
    w("#ec  (T_flex/T_fijo)^2 = 1 + k/K_x + k*h^2/K_yy | (2-1)")
    w("#ec  k = 3*E*I/h^3")
    w("# Se calcula el periodo con OpenSees (`eigen`) y se compara con esa fórmula para varios suelos, de blando a duro.")
    w("#hide")
    w(lib)
    w("""
# ---- la estructura: columna de h = 4 m con masa en la punta, empotrada en el nudo maestro de la zapata ----
set E 2.5e7
set b 0.5
set h 4.0
set M 20.0
set A [expr {$b*$b}]
set I [expr {pow($b,4)/12.0}]
set J [expr {0.141*pow($b,4)}]
set G0 [expr {$E/(2*(1+0.2))}]
set k [expr {3.0*$E*$I/pow($h,3)}]
set Tfijo [expr {6.283185307179586*sqrt($M/$k)}]
set Bz 1.5          ;# mitad del lado corto de la zapata
set Lz 2.0          ;# mitad del lado largo
set nuS 0.35
set rhoS 1.8
# periodo con el suelo (OpenSees): Vs en m/s, D = empotramiento de la zapata (m)
proc periodo {Vs D} {
    global E A I J G0 h M Bz Lz nuS rhoS
    set G [expr {$rhoS*$Vs*$Vs}]
    wipe
    model basic -ndm 3 -ndf 6
    set K [ise_K $G $nuS $Bz $Lz $D]
    # nudos: 1 = base de la columna, 2 = punta; el maestro de la zapata es el 10 y la tierra el 11
    node 1 0.0 0.0 0.0
    node 2 0.0 0.0 $h
    geomTransf Linear 1 1 0 0
    element elasticBeamColumn 1 1 2 $A $E $G0 $J $I $I 1
    mass 2 $M $M $M 0.0 0.0 0.0
    ise_cimentacion 10 0.0 0.0 0.0 $K {1}
    set lam [eigen -fullGenLapack 3]
    set res {}
    foreach l $lam { lappend res [expr {6.283185307179586/sqrt($l)}] }
    return [list $K $res]
}
# la fórmula cerrada del NIST (1 grado de libertad por dirección: traslación + giro de la base)
proc periodo_nist {Vs D} {
    global E I h M Bz Lz nuS rhoS k Tfijo
    set G [expr {$rhoS*$Vs*$Vs}]
    set K [ise_K $G $nuS $Bz $Lz $D]
    lassign $K Kx Ky Kz Kxx Kyy Kzz
    # movimiento en x: traslacion Kx + giro Kyy;  movimiento en y: traslacion Ky + giro Kxx.  Gobierna el periodo mayor.
    set Tx [expr {$Tfijo*sqrt(1.0 + $k/$Kx + $k*$h*$h/$Kyy)}]
    set Ty [expr {$Tfijo*sqrt(1.0 + $k/$Ky + $k*$h*$h/$Kxx)}]
    return [expr {max($Tx,$Ty)}]
}
puts "HEKATAN:T_fijo_s=$Tfijo"
foreach Vs {100 150 200 300 400} {
    lassign [periodo $Vs 0.0] K T
    set Tn [periodo_nist $Vs 0.0]
    # el modo 1 es el de flexion en uno de los dos ejes; el de menor Kyy (giro) es el que gobierna: se toma el mayor periodo
    set To [lindex [lsort -real -decreasing $T] 0]
    puts "HEKATAN:T_Vs${Vs}_OpenSees=$To"
    puts "HEKATAN:T_Vs${Vs}_NIST=$Tn"
    puts "HEKATAN:dif_Vs${Vs}_pct=[expr {100.0*($To-$Tn)/$Tn}]"
    puts "HEKATAN:razon_Vs${Vs}=[expr {$To/$Tfijo}]"
}
lassign [periodo 200 0.0] K T
puts "HEKATAN:Kx_Vs200_kNm=[lindex $K 0]"
puts "HEKATAN:Kz_Vs200_kNm=[lindex $K 2]"
puts "HEKATAN:Kyy_Vs200_kNm_rad=[lindex $K 4]"
lassign [periodo 200 1.0] K T
puts "HEKATAN:Kx_Vs200_D1_kNm=[lindex $K 0]"
puts "HEKATAN:Kyy_Vs200_D1_kNm_rad=[lindex $K 4]"
""")
    w("#show")
    w("## Resultados")
    w("# Para cada suelo: periodo de OpenSees, periodo de la fórmula del NIST y su diferencia. Con el suelo más blando el periodo se alarga más.")
    w("#values")
    w("#resumen El suelo **alarga el periodo**: con Vs = 100 m/s la estructura vibra bastante más lento que con la base fija. OpenSees y la fórmula del NIST coinciden porque usan **los mismos muelles**.")
    open(out, "w", encoding="utf-8", newline="\n").write("\n".join(W) + "\n")
    print("escrito", out)


if __name__ == "__main__":
    main()
