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
