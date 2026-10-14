# -*- coding: utf-8 -*-
"""Corrobora un script OpenSees: lo corre con Hekatan OpenSees (la DLL de Petracca y Camata) y con el OpenSees oficial
(OpenSees.exe) y compara los valores que el script exporta con `puts "HEKATAN:nombre=valor"`.

    python corroborar.py modelo.tcl

El juez es OTRO programa: HK_OPENSEES_EXE, o C:\\OpenSees3.7.1\\OpenSees3.7.1\\bin\\OpenSees.exe, o el que esté en el PATH."""
import os, re, shutil, subprocess, sys, tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))


def exportados(texto):
    d = {}
    for ln in texto.splitlines():
        m = re.match(r"\s*(?:HEKATAN|CALCPAD):\s*([^=\s]+)\s*=\s*(\S+)", ln)
        if m:
            try: d[m.group(1)] = float(m.group(2))
            except ValueError: pass
    return d


def con_hekatan(src):
    sys.path.insert(0, AQUI)
    import oscalc
    out, err, _ = oscalc.run_opensees(src)
    return exportados(out), err


def buscar_exe():
    for c in (os.environ.get("HK_OPENSEES_EXE"), r"C:\OpenSees3.7.1\OpenSees3.7.1\bin\OpenSees.exe",
              shutil.which("OpenSees"), shutil.which("OpenSees.exe")):
        if c and os.path.exists(c): return c
    return None


def con_oficial(exe, tcl):
    # en el OpenSees oficial `puts` imprime a stdout; se corre en una carpeta aparte para no ensuciar la del modelo
    with tempfile.TemporaryDirectory() as d:
        p = subprocess.run([exe, tcl], cwd=d, capture_output=True, text=True, timeout=300, errors="replace", stdin=subprocess.DEVNULL)
    salida = p.stdout + chr(10) + p.stderr
    malas = [l.strip() for l in salida.splitlines() if re.search(r"invalid command name|can.t read|wrong # args|ERROR|syntax error", l, re.I)]
    return exportados(salida), ("; ".join(malas[:3]) if malas else "")


def main():
    tcl = os.path.abspath(sys.argv[1])
    src = open(tcl, encoding="utf-8").read()
    a, err_a = con_hekatan(src)
    print("Hekatan OpenSees (DLL de Petracca y Camata):", ", ".join(f"{k}={v:.8g}" for k, v in a.items()) or "(sin valores exportados)")
    if err_a: print("  aviso:", err_a[:300])
    exe = buscar_exe()
    if not exe:
        print("No encuentro el OpenSees oficial (OpenSees.exe). Define HK_OPENSEES_EXE con su ruta."); return 2
    b, err_b = con_oficial(exe, tcl)
    print("OpenSees oficial (%s):" % exe, ", ".join(f"{k}={v:.8g}" for k, v in b.items()) or "(sin valores exportados)")
    if err_b: print("  ERROR en el OpenSees oficial:", err_b[:300])
    if not a or not b:
        print("Falta exportar valores: agrega al script  puts \"HEKATAN:nombre=[valor]\""); return 3
    print("\n%-16s %16s %16s %12s" % ("valor", "Hekatan", "oficial", "dif. %"))
    peor = 0.0
    for k in a:
        if k in b:
            dif = abs(a[k] - b[k]) / max(abs(b[k]), 1e-6) * 100
            peor = max(peor, dif)
            print("%-16s %16.8g %16.8g %12.2e" % (k, a[k], b[k], dif))
    print("\nResultado:", "CORROBORADO (dif. máx %.2e %%)" % peor if peor < 1e-4 else "DIFERENCIA %.3e %% — revisar" % peor)
    return 0 if peor < 1e-4 else 1


if __name__ == "__main__":
    sys.exit(main())
