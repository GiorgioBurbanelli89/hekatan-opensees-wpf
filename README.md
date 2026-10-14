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

## Motor de cálculo (no incluido aquí)

Los cálculos los hace el **solver de Massimo Petracca y Guido Camata** sobre **OpenSees** (sus aportes son públicos, de ellos).
Este repositorio **no redistribuye** ese motor ni OpenSees: contiene solo la interfaz, los scripts de reporte
(`oscalc.py`, `corroborar.py`, `ecuacion.py`, `hk_ops.py`) y los ejemplos. Para ejecutar necesitas tu propia copia del motor
(la DLL embebida se busca en `..	est`, ver el `.csproj`) y, para **Corroborar**, el `OpenSees.exe` oficial.
OpenSees es © The Regents of the University of California; revisa su licencia
(<https://github.com/OpenSees/OpenSees/blob/master/COPYRIGHT>) antes de redistribuirlo.

## Créditos

Massimo Petracca y Guido Camata (solver y elementos), OpenSees (UC Berkeley, PEER).

## Terceros incluidos

Plotly.js (MIT), vtk.js (BSD-3-Clause); AvalonEdit (MIT) y WebView2 vía NuGet.

## Licencia

MIT, © 2026 Hekatan Engineers (Giorgio Burbanelli). Ver `LICENSE`.
