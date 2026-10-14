#title Dibujo 2D y 3D (como Hekatan LISP)
## Modelo de OpenSees
# Un pórtico plano de 6 m por 3 m. El bloque **#dibujar** de abajo lo dibuja *con el cursor*: gira con el botón izquierdo, zoom con la rueda, mueve con Mayús.
wipe
model basic -ndm 2 -ndf 3
node 1 0 0
node 2 6 0
node 3 0 3
node 4 6 3
fix 1 1 1 1
fix 2 1 1 1
geomTransf Linear 1
element elasticBeamColumn 1 1 3 0.09 25000000 6.75e-4 1
element elasticBeamColumn 2 2 4 0.09 25000000 6.75e-4 1
element elasticBeamColumn 3 3 4 0.09 25000000 6.75e-4 1
timeSeries Linear 1
pattern Plain 1 1 { load 3 20 0 0 }
#hide
constraints Plain
numberer RCM
system BandSPD
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
#show
puts "HEKATAN:ux_techo_mm=[expr {[nodeDisp 3 1]*1000}]"
## Dibujo
# Pulsa **Línea**, **Cara** o **Círculo**, o escribe en la línea de órdenes: `LINEA`, `0,0,0`, `@5,0,0`. Lo que dibujes se escribe aquí abajo como `# linea …`; **Guardar DWG** lo manda a AutoCAD.
#dibujar
# modelo
# capa DIBUJO
# linea 0 0 0  6 0 0
# caja 7 0 0  1 1 1
#enddibujar
