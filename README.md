# Hekatan OpenSees (WPF)

Editor de scripts **OpenSees (Tcl)** con el reporte al lado, para Windows (.NET 10, WPF + WebView2).
Escribes o eliges un ejemplo, el **AutoRun** calcula solo y el reporte muestra el modelo, la deformada con color,
las tablas de desplazamientos y los valores exportados con `puts "HEKATAN:nombre=valor"`.

- Menús que insertan comandos de OpenSees (Modelo, Materiales, Elementos, Cargas, Análisis, Gráficas, Resultados).
- **Ejemplos**: voladizo, pórticos, muro, galpón, taludes y un submenú **Cimentaciones y suelo-estructura**
  (funciones de impedancia NIST GCR 12-917-21, zapata rígida sobre Winkler).
- **Corroborar**: corre el mismo script en el `OpenSees.exe` oficial y compara los valores.
- Exportar el reporte a HTML o PNG; tema oscuro y claro; canal de pruebas `--ctl` (ver `MainWindow.Ctl.cs`).

## Compilar

```
dotnet build HekatanOpenSees.csproj -c Release
```

## Qué NO incluye este repositorio

El **motor de cálculo OpenSees** (la DLL / el ejecutable) **no se distribuye aquí**. OpenSees es © The Regents of the University
of California y su licencia limita la redistribución comercial
(<https://github.com/OpenSees/OpenSees/blob/master/COPYRIGHT>). Para ejecutar los cálculos necesitas tu propia copia de OpenSees
(el `OpenSees.exe` oficial para **Corroborar**; la DLL embebida se busca en `..\test`, ver el `.csproj`).
El repositorio contiene solo la interfaz, los scripts de reporte (`oscalc.py`, `corroborar.py`, `ecuacion.py`, `hk_ops.py`)
y los ejemplos.

## Terceros incluidos

Plotly.js (MIT), vtk.js (BSD-3-Clause); AvalonEdit (MIT) y WebView2 vía NuGet.

## Licencia

MIT, © 2026 Hekatan Engineers (Giorgio Burbanelli). Ver `LICENSE`.
