# Portico espacial 3D — 4 columnas + vigas en cabeza, carga lateral en el techo.
# Sirve para ver el visor vtk.js ORBITABLE de la deformada (ndm 3).
wipe
model basic -ndm 3 -ndf 6

# --- nudos: base (1-4) y techo (5-8), planta 4x4 m, altura 3 m ---
node 1  0 0 0
node 2  4 0 0
node 3  4 4 0
node 4  0 4 0
node 5  0 0 3
node 6  4 0 3
node 7  4 4 3
node 8  0 4 3

# --- empotramiento en la base ---
fix 1 1 1 1 1 1 1
fix 2 1 1 1 1 1 1
fix 3 1 1 1 1 1 1
fix 4 1 1 1 1 1 1

# --- seccion elastica (columna/viga de hormigon 0.3x0.3) ---
set E 2.5e10
set G 1.0e10
set A 0.09
set Iz 6.75e-4
set Iy 6.75e-4
set J 1.14e-3

geomTransf Linear 1 0 1 0
geomTransf Linear 2 0 0 1

# columnas (transf 1)
element elasticBeamColumn 1 1 5 $A $E $G $J $Iy $Iz 1
element elasticBeamColumn 2 2 6 $A $E $G $J $Iy $Iz 1
element elasticBeamColumn 3 3 7 $A $E $G $J $Iy $Iz 1
element elasticBeamColumn 4 4 8 $A $E $G $J $Iy $Iz 1
# vigas de techo (transf 2)
element elasticBeamColumn 5 5 6 $A $E $G $J $Iy $Iz 2
element elasticBeamColumn 6 6 7 $A $E $G $J $Iy $Iz 2
element elasticBeamColumn 7 7 8 $A $E $G $J $Iy $Iz 2
element elasticBeamColumn 8 8 5 $A $E $G $J $Iy $Iz 2

# --- carga lateral en X sobre los 4 nudos del techo ---
timeSeries Linear 1
pattern Plain 1 1 {
    load 5 50000 0 0 0 0 0
    load 6 50000 0 0 0 0 0
    load 7 50000 0 0 0 0 0
    load 8 50000 0 0 0 0 0
}

system BandGeneral
numberer RCM
constraints Plain
integrator LoadControl 1
algorithm Linear
analysis Static
analyze 1

set ux [nodeDisp 5 1]
puts "HEKATAN:ux_techo=[expr $ux*1000] mm"
