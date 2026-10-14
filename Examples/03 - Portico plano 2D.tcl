#title Pórtico 2D — 1 vano, 1 piso
## Modelo
# Pórtico de 6 m de ancho y 3 m de alto. Carga lateral de 20 kN en el techo.
# Columnas y viga: 0.30x0.30 m (A=0.09 m², I=6.75e-4 m⁴), E=2.5e7 kN/m² (hormigón).
wipe
model basic -ndm 2 -ndf 3
node 1 0 0
node 2 6 0
node 3 0 3
node 4 6 3
fix 1 1 1 1
fix 2 1 1 1
geomTransf Linear 1
#-- columnas izquierda y derecha
element elasticBeamColumn 1 1 3 0.09 25000000 6.75e-4 1
element elasticBeamColumn 2 2 4 0.09 25000000 6.75e-4 1
#-- viga de techo
element elasticBeamColumn 3 3 4 0.09 25000000 6.75e-4 1
timeSeries Linear 1
pattern Plain 1 1 { load 3 20 0 0 }
#hide
constraints Plain
numberer RCM
system BandSPD
#show
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
## Deformada (desplazamiento lateral del pórtico)
#plot
## Desplazamientos nodales
#disp
puts "HEKATAN:ux_techo_mm=[expr {[nodeDisp 3 1]*1000}]"
