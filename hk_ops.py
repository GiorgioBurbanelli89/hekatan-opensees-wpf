# -*- coding: utf-8 -*-
"""OpenSees de Hekatan: la DLL compilada del clon oficial (hekatan-opensees/test/OpenSees.dll) cargada en un intérprete Tcl, con la
MISMA interfaz que openseespy (`ops.node(...)`, `ops.element(...)`, ...). Así el guion del muro es el mismo con pip o con la DLL.

    import hk_ops as ops          # en vez de  import openseespy.opensees as ops

Cada llamada se vuelve una orden Tcl (`node 1 0.0 0.0`); lo que devuelve el Tcl se convierte a número o lista de números."""
import os, tkinter

def _buscar(rel):
    """Sube por las carpetas hasta encontrar `rel` (hekatan-opensees/test/... o test/...)."""
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        for pre in ("", "hekatan-opensees"):
            p = os.path.join(d, pre, rel)
            if os.path.exists(p): return p
        d = os.path.dirname(d)
    return os.path.join("test", rel)


DLL = os.environ.get("HK_OPENSEES_DLL") or _buscar(os.path.join("test", "OpenSees.dll"))
# LAPACK/BLAS de 32 bits (LP64): la DLL se compiló con enteros de 32 bits y la liblapack de Octave es de 64 (ILP64) -> «parameter number N is invalid».
# test/lp64 = libopenblas.dll de Hekatan Lab + la misma como liblapack.dll; va delante de la de Octave.
# Intel oneMKL 2024 de Hekatan Lab (test/lp64mkl: mkl_rt.2.dll renombrada liblapack.dll, 27 % mas rapido y mismos resultados);
# si no esta, la libopenblas de 32 bits (test/lp64)
_mkl = _buscar(os.path.join("test", "lp64mkl", "liblapack.dll"))
LAPACK = os.environ.get("HK_LAPACK_DIR") or os.path.dirname(_mkl if os.path.exists(_mkl) else _buscar(os.path.join("test", "lp64", "libopenblas.dll")))
os.environ["PATH"] = LAPACK + ";" + os.path.dirname(DLL) + ";C:/Program Files/GNU Octave/Octave-10.1.0/mingw64/bin;" + os.environ.get("PATH", "")
_T = tkinter.Tcl()
_T.eval("load {%s}" % DLL.replace("\\", "/"))


def _num(x):
    try: return float(x)
    except ValueError: return x


def _llamar(nombre, *args):
    args = [a.item() if hasattr(a, "item") else a for a in args]          # numpy → Python (repr de np.float64 no es un número para Tcl)
    r = _T.eval(nombre + " " + " ".join(repr(a) if isinstance(a, float) else str(a) for a in args))
    partes = r.split()
    if not partes: return None
    return _num(partes[0]) if len(partes) == 1 else [_num(p) for p in partes]


def __getattr__(nombre):
    if nombre.startswith("__"): raise AttributeError(nombre)
    return lambda *a: _llamar(nombre, *a)


def version():
    return _T.eval("version")
