#title Zapata rígida sobre muelles de Winkler
## Qué se calcula
# Una **zapata aislada** de 2.0 × 2.0 m sobre un suelo con **coeficiente de balasto** ks = 6.59 kg/cm³ (el del estudio de suelos de Manabí). Carga la columna: **N = 500 kN** vertical y **M = 100 kN·m** de momento.
# El suelo se modela con **muelles de Winkler**: 11 muelles verticales repartidos en el ancho, cada uno con la rigidez de su área tributaria. La zapata es una viga **rígida**.
# Para una zapata rígida la respuesta tiene solución cerrada: el asentamiento es **u = N / Σk** y el giro es **θ = M / Σ(k·x²)**. Aquí se compara con OpenSees.
#hide
wipe
model basic -ndm 2 -ndf 3
set B 2.0; set L 2.0; set n 10
set ks 64620.0
set N 500.0; set M 100.0
set dx [expr {$B/$n}]
# nudos de la zapata (1..11) y del terreno (101..111, fijos)
for {set i 0} {$i <= $n} {incr i} {
    set x [expr {-$B/2.0 + $i*$dx}]
    node [expr {1+$i}] $x 0.0
    node [expr {101+$i}] $x 0.0
    fix [expr {101+$i}] 1 1 1
}
# viga rígida
uniaxialMaterial Elastic 1 1.0
geomTransf Linear 1
for {set i 1} {$i <= $n} {incr i} {
    element elasticBeamColumn $i $i [expr {$i+1}] 100.0 1.0e8 1.0e4 1
}
# muelles de Winkler: k_i = ks * L * ancho tributario (la mitad en los extremos)
set sk 0.0; set skx2 0.0
for {set i 0} {$i <= $n} {incr i} {
    set w $dx
    if {$i == 0 || $i == $n} { set w [expr {$dx/2.0}] }
    set k [expr {$ks*$L*$w}]
    set x [expr {-$B/2.0 + $i*$dx}]
    set sk [expr {$sk + $k}]
    set skx2 [expr {$skx2 + $k*$x*$x}]
    uniaxialMaterial Elastic [expr {1000+$i}] $k
    element zeroLength [expr {50+$i}] [expr {101+$i}] [expr {1+$i}] -mat [expr {1000+$i}] -dir 2
}
# carga de la columna en el centro de la zapata (nudo 6)
timeSeries Linear 1
pattern Plain 1 1 { load 6 0.0 -500.0 100.0 }
system BandSPD
numberer RCM
constraints Plain
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
set uy [expr {[nodeDisp 6 2]*1000.0}]
set th [nodeDisp 6 3]
set uy_t [expr {-$N/$sk*1000.0}]
set th_t [expr {$M/$skx2}]
puts "HEKATAN:asentamiento_mm=$uy"
puts "HEKATAN:asentamiento_teorico_mm=$uy_t"
puts "HEKATAN:giro_rad=$th"
puts "HEKATAN:giro_teorico_rad=$th_t"
#show
## Resultados
# Con la **suma de rigideces** Σk del suelo la zapata baja un valor **u** (asentamiento) y gira un ángulo **θ** por el momento. OpenSees y la fórmula cerrada dan lo mismo.
#values
