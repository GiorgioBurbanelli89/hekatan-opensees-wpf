#title Plotly en Hekatan OpenSees
## Voladizo con gráficas de Plotly
# Las líneas **#** dentro de `#gfx` son código de gráficas (como en Hekatan Lab); *OpenSees las ignora*.
## La flecha de un voladizo
# Con carga puntual P en la punta, la flecha y la curva elástica son:
#ec  delta = P*L^3/(3*E*I) | #
#ec  w_x = P*x^2/(6*E*I)*(3*L - x) | #
#ec  sigma_max = M*c/I = 6*P*L/(b*h^2)
# Aquí P = 10 kN, L = 5 m, E = 2.1e8 kN/m² e I = 8.333e-5 m⁴.
wipe
model basic -ndm 2 -ndf 3
node 1 0 0
node 2 5 0
fix 1 1 1 1
geomTransf Linear 1
element elasticBeamColumn 1 1 2 0.01 210000000 0.00008333 1
timeSeries Linear 1
pattern Plain 1 1 { load 2 0 -10 0 }
#hide
constraints Plain
numberer RCM
system BandSPD
integrator LoadControl 1.0
algorithm Linear
analysis Static
analyze 1
#show
puts "HEKATAN:uy_mm=[expr {[nodeDisp 2 2]*1000}]"
## Flecha w(x) con Plotly (hover, zoom)
#gfx
# var x=linspace(0,5,40); var w=x.map(function(t){return uy_mm*(3*t*t-t*t*t/5)/(2*25);});
# plotlyPlot(x, w, 'Flecha de la viga', 'x [m]', 'w [mm]');
#endgfx
## Superficie 3D (gíralo con el ratón)
#gfx
# var gx=linspace(-3,3,30), gy=linspace(-3,3,30), Z=[];
# for(var i=0;i<gy.length;i++){Z[i]=[];for(var j=0;j<gx.length;j++){Z[i][j]=Math.exp(-(gx[j]*gx[j]+gy[i]*gy[i])/4)*Math.cos(gx[j]);}}
# plotlySurf(gx, gy, Z, 'Z = e^(-r²/4)·cos(x)');
#endgfx
#resumen La **flecha** de un voladizo es *P·L³/(3·E·I)*; la corroboramos con el OpenSees oficial.
