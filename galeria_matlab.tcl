#title Galería de gráficas MATLAB (motor embebido)
## Modelo OpenSees
# Voladizo de 5 m con carga puntual de 10 kN en la punta.
# El resultado (uy_mm) se grafica abajo con funciones de nombre MATLAB.
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
## Deformada (motor Hekatan OpenSees)
#plot
#values
puts "HEKATAN:uy_mm=[expr {[nodeDisp 2 2]*1000}]"

## Gráficas con la API de MATLAB (todo embebido, sin script externo)
# Las líneas '#' son comentarios para OpenSees; Hekatan OpenSees las dibuja.
#gfx
# figure(); var x=linspace(0,5,40);
# var w=x.map(function(t){return uy_mm*(3*t*t-t*t*t/5)/(2*25);});
# plot(x,w,'r-'); title('Flecha de la viga (usa uy_mm de OpenSees)'); xlabel('x [m]'); ylabel('w [mm]'); grid('on'); datacursor('w mm');
#endgfx
#gfx
# figure(); bar([1,2,3,4,5],[3,7,2,5,4]); title('bar'); xlabel('caso'); ylabel('valor');
#endgfx
#gfx
# figure(); var gx=linspace(-3,3,28), gy=linspace(-3,3,28);
# var Z=[]; for(var i=0;i<gy.length;i++){Z[i]=[];for(var j=0;j<gx.length;j++){var r=gx[j]*gx[j]+gy[i]*gy[i];Z[i][j]=Math.exp(-r/4)*Math.cos(2*Math.sqrt(r));}}
# contourf(gx,gy,Z,12); title('contourf'); axis('equal');
#endgfx
#gfx
# figure(); var gx2=linspace(-3,3,24), gy2=linspace(-3,3,24); var mg=meshgrid(gx2,gy2);
# var Z2=[]; for(var i=0;i<gy2.length;i++){Z2[i]=[];for(var j=0;j<gx2.length;j++){var r=gx2[j]*gx2[j]+gy2[i]*gy2[i];Z2[i][j]=Math.exp(-r/4)*Math.cos(2*Math.sqrt(r));}}
# surf(mg[0],mg[1],Z2); title('surf 3D (arrastra para girar)');
#endgfx
