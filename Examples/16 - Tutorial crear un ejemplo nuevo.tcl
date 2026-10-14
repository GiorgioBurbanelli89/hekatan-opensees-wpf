#title Tutorial: cómo crear un ejemplo nuevo en OpenSees
## Qué vamos a hacer
# Una **viga simplemente apoyada** de 6 m con una **carga uniforme de 10 kN/m**, en 7 pasos. Cada paso es un bloque del script; con el **AutoRun** el reporte se actualiza solo al escribir.
# Al final se compara con la solución a mano: flecha **5·w·L⁴ / (384·E·I)**, momento **w·L²/8** y reacciones **w·L/2**.
## Paso 1 · El modelo
# `wipe` borra lo anterior y `model basic` fija las dimensiones: 2 dimensiones y 3 grados de libertad por nudo (ux, uy, giro).
wipe
model basic -ndm 2 -ndf 3
## Paso 2 · Datos y nudos
# Se definen los datos con `set` y los **5 nudos** a lo largo de la viga (4 elementos de 1.5 m).
set L 6.0
set w 10.0
set E 2.1e8
set I 8.333e-5
set A 0.01
for {set i 0} {$i <= 4} {incr i} {
    node [expr {$i+1}] [expr {$i*$L/4.0}] 0.0
}
## Paso 3 · Apoyos
# `fix` restringe grados de libertad (1 = fijo): articulación en el nudo 1 y apoyo móvil en el nudo 5.
fix 1 1 1 0
fix 5 0 1 0
## Paso 4 · Elementos
# Una transformación geométrica y 4 elementos `elasticBeamColumn` con su área, módulo e inercia.
geomTransf Linear 1
for {set i 1} {$i <= 4} {incr i} {
    element elasticBeamColumn $i $i [expr {$i+1}] $A $E $I 1
}
## Paso 5 · Carga
# Una serie de tiempo lineal y un patrón con carga **uniforme hacia abajo** sobre los 4 elementos.
timeSeries Linear 1
pattern Plain 1 1 {
    eleLoad -ele 1 2 3 4 -type -beamUniform [expr {-$w}]
}
## Paso 6 · Análisis
# Un análisis estático lineal de un solo paso.
system BandSPD
numberer RCM
constraints Plain
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
## Paso 7 · Resultados y comparación
# Se lee la flecha del centro (nudo 3) y la reacción del apoyo (nudo 1) y se comparan con la fórmula. Las líneas `puts "HEKATAN:..."` aparecen en el reporte y las usa **Corroborar**.
reactions
set uy [expr {[nodeDisp 3 2]*1000.0}]
set uy_t [expr {-5.0*$w*pow($L,4)/(384.0*$E*$I)*1000.0}]
set R1 [nodeReaction 1 2]
set R1_t [expr {$w*$L/2.0}]
puts "HEKATAN:flecha_mm=$uy"
puts "HEKATAN:flecha_teorica_mm=$uy_t"
puts "HEKATAN:reaccion_kN=$R1"
puts "HEKATAN:reaccion_teorica_kN=[expr {$R1_t}]"
#show
## Resultado
# La flecha en el centro y la reacción coinciden con la solución a mano **w·L/2 = 30 kN** y **5·w·L⁴/384·E·I**.
#values
