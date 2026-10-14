# Viga en voladizo 2D — carga puntual en la punta
# E=2.1e8 kN/m2, I=8.333e-5 m4, A=0.01 m2, L=5 m, P=10 kN
wipe
model basic -ndm 2 -ndf 3
# Nodos
node 1 0 0
node 2 5 0
# Empotramiento en el nodo 1
fix 1 1 1 1
# Elemento viga elastica
geomTransf Linear 1
element elasticBeamColumn 1 1 2 0.01 210000000 0.00008333 1
# Carga de 10 kN hacia abajo en la punta
timeSeries Linear 1
pattern Plain 1 1 { load 2 0 -10 0 }
# Analisis estatico lineal
system BandSPD
numberer RCM
constraints Plain
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
# Resultados
set uy [expr {[nodeDisp 2 2]*1000}]
set rot [nodeDisp 2 3]
puts "Deflexion en la punta:"
puts "  uy = $uy mm"
puts "  giro = $rot rad"
puts "HEKATAN:uy_mm=$uy"
puts "HEKATAN:giro_rad=$rot"
