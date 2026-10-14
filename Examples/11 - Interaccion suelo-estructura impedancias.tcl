#title Interacción suelo-estructura con funciones de impedancia
## Qué se calcula
# Una **columna** de hormigón de 0.50 × 0.50 m y 4 m de alto, con una masa de 20 t en la punta, apoyada en una **zapata rígida** de 3.0 × 4.0 m sobre un suelo con velocidad de onda de corte *Vs*.
# El suelo no se dibuja: se sustituye por los **6 muelles de la zapata** (traslación en x, y, z y giro en x, y, z). Sus rigideces salen de las *funciones de impedancia* del **NIST GCR 12-917-21** (Pais y Kausel, 1988).
# Con base fija el periodo es T; con el suelo se alarga a T~. El NIST da la razón de periodos de una forma cerrada:
#ec  (T_flex/T_fijo)^2 = 1 + k/K_x + k*h^2/K_yy | (2-1)
#ec  k = 3*E*I/h^3
# Se calcula el periodo con OpenSees (`eigen`) y se compara con esa fórmula para varios suelos, de blando a duro.
#hide
# ---- Funciones de impedancia de la cimentación (NIST GCR 12-917-21, cap. 2: Pais y Kausel 1988) ----
# Zapata rígida rectangular: B = MITAD del ancho (lado corto, eje y), L = MITAD del largo (lado largo, eje x), L >= B.
# G = módulo cortante del suelo (ya reducido por deformación, Tabla 2-1), nu = Poisson, D = profundidad de empotramiento.
#   K[0..5] = Kx Ky Kz  Kxx Kyy Kzz   (rigideces estáticas, con el factor de empotramiento de la Tabla 2-2b)
proc ise_K {G nu B L D} {
    set r [expr {double($L)/$B}]
    # Tabla 2-2a: zapata en la superficie
    set Kz  [expr {$G*$B/(1-$nu)*(3.1*pow($r,0.75)+1.6)}]
    set Ky  [expr {$G*$B/(2-$nu)*(6.8*pow($r,0.65)+0.8*$r+1.6)}]
    set Kx  [expr {$G*$B/(2-$nu)*(6.8*pow($r,0.65)+2.4)}]
    set Kzz [expr {$G*pow($B,3)*(4.25*pow($r,2.45)+4.06)}]
    set Kyy [expr {$G*pow($B,3)/(1-$nu)*(3.73*pow($r,2.4)+0.27)}]
    set Kxx [expr {$G*pow($B,3)/(1-$nu)*(3.2*$r+0.8)}]
    # Tabla 2-2b: factores de empotramiento (Pais y Kausel)
    set d [expr {double($D)/$B}]
    set ez  [expr {1.0+(0.25+0.25/$r)*pow($d,0.8)}]
    set ey  [expr {1.0+(0.33+1.34/(1+$r))*pow($d,0.8)}]
    set ezz [expr {1.0+(1.3+1.32/$r)*pow($d,0.9)}]
    set eyy [expr {1.0+$d+(1.6/(0.35+pow($r,4)))*pow($d,2)}]
    set exx [expr {1.0+$d+(1.6/(0.35+$r))*pow($d,2)}]
    return [list [expr {$ey*$Kx}] [expr {$ey*$Ky}] [expr {$ez*$Kz}] [expr {$exx*$Kxx}] [expr {$eyy*$Kyy}] [expr {$ezz*$Kzz}]]
}
# Modificadores dinámicos (Tabla 2-3a, zapata en la superficie) y amortiguamiento por radiación; a0 = omega*B/Vs
#   devuelve  {alfa_x alfa_y alfa_z alfa_xx alfa_yy alfa_zz  beta_x beta_y beta_z beta_xx beta_yy beta_zz}
proc ise_dinamico {G nu B L a0} {
    set r [expr {double($L)/$B}]
    set psi [expr {min(2.5, sqrt(2.0*(1-$nu)/(1-2*$nu)))}]
    set a02 [expr {$a0*$a0}]
    set az  [expr {1.0-((0.4+0.2/$r)*$a02)/(10.0/(1+3*($r-1))+$a02)}]
    set azz [expr {1.0-((0.33-0.03*sqrt($r-1))*$a02)/(0.8/(1+0.33*($r-1))+$a02)}]
    set ayy [expr {1.0-(0.55*$a02)/((0.6+1.4/pow($r,3))+$a02)}]
    set axx [expr {1.0-((0.55+0.01*sqrt($r-1))*$a02)/((2.4-0.4/pow($r,3))+$a02)}]
    set Kz  [expr {$G*$B/(1-$nu)*(3.1*pow($r,0.75)+1.6)}]
    set Ky  [expr {$G*$B/(2-$nu)*(6.8*pow($r,0.65)+0.8*$r+1.6)}]
    set Kx  [expr {$G*$B/(2-$nu)*(6.8*pow($r,0.65)+2.4)}]
    set Kzz [expr {$G*pow($B,3)*(4.25*pow($r,2.45)+4.06)}]
    set Kyy [expr {$G*pow($B,3)/(1-$nu)*(3.73*pow($r,2.4)+0.27)}]
    set Kxx [expr {$G*pow($B,3)/(1-$nu)*(3.2*$r+0.8)}]
    set bz  [expr {(4*$psi*$r/($Kz/($G*$B)))*($a0/(2*$az))}]
    set by  [expr {(4*$r/($Ky/($G*$B)))*($a0/2.0)}]
    set bx  [expr {(4*$r/($Kx/($G*$B)))*($a0/2.0)}]
    set bzz [expr {((4.0/3)*(pow($r,3)+$r)*$a02/(($Kzz/($G*pow($B,3)))*((1.4/pow(1+3*($r-1),0.7))+$a02)))*($a0/(2*$azz))}]
    set byy [expr {((4*$psi/3)*pow($r,3)*$a02/(($Kyy/($G*pow($B,3)))*((1.8/(1+1.75*($r-1)))+$a02)))*($a0/(2*$ayy))}]
    set bxx [expr {((4*$psi/3)*$r*$a02/(($Kxx/($G*pow($B,3)))*((2.2-0.4/pow($r,3))+$a02)))*($a0/(2*$axx))}]
    return [list 1.0 1.0 $az $axx $ayy $azz $bx $by $bz $bxx $byy $bzz]
}
# Cimentación rígida: los nudos de la base se atan a un nudo maestro (centro de la zapata) y éste a la tierra con 6 muelles.
#   K = {Kx Ky Kz Kxx Kyy Kzz}; basesNudos = nudos de la estructura que apoyan en la zapata; devuelve el nudo maestro
proc ise_cimentacion {idMaestro xc yc zc K basesNudos {idTierra 0}} {
    if {$idTierra == 0} { set idTierra [expr {$idMaestro + 1}] }
    node $idMaestro $xc $yc $zc
    node $idTierra $xc $yc $zc
    fix $idTierra 1 1 1 1 1 1
    foreach nb $basesNudos { rigidLink beam $idMaestro $nb }
    set k 0
    set dirs {}
    set mats {}
    foreach Ki $K {
        incr k
        set m [expr {900000 + $idMaestro*10 + $k}]
        uniaxialMaterial Elastic $m $Ki
        lappend dirs $k
        lappend mats $m
    }
    element zeroLength [expr {900000 + $idMaestro}] $idTierra $idMaestro -mat {*}$mats -dir {*}$dirs
    return $idMaestro
}


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

#show
## Resultados
# Para cada suelo: periodo de OpenSees, periodo de la fórmula del NIST y su diferencia. Con el suelo más blando el periodo se alarga más.
#values
#resumen El suelo **alarga el periodo**: con Vs = 100 m/s la estructura vibra bastante más lento que con la base fija. OpenSees y la fórmula del NIST coinciden porque usan **los mismos muelles**.
