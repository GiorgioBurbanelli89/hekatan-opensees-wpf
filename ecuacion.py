# -*- coding: utf-8 -*-
"""Ecuaciones con el formato de Hekatan LISP (m-var cursiva azul, fracciones apiladas, potencias, subindices, raices) a partir de una
formula escrita en una linea:  #ec  w = P*L^3/(3*E*I)   ·   #ec  sigma_max = M*c/I   ·   #ec  e = sqrt(a^2 + b^2)

    a/b            fraccion apilada         x^2, x^(n+1)   potencia          x_i, x_max   subindice
    sqrt(x)        raiz                     pi alpha beta ... letras griegas  *  producto (punto medio)
Es solo la presentacion: el calculo lo hace OpenSees (o #gfx)."""
import html, re

GRIEGAS = {n: c for n, c in (
    ("alpha", "α"), ("beta", "β"), ("gamma", "γ"), ("delta", "δ"), ("epsilon", "ε"), ("zeta", "ζ"), ("eta", "η"), ("theta", "θ"),
    ("lambda", "λ"), ("mu", "μ"), ("nu", "ν"), ("xi", "ξ"), ("pi", "π"), ("rho", "ρ"), ("sigma", "σ"), ("tau", "τ"), ("phi", "φ"),
    ("chi", "χ"), ("psi", "ψ"), ("omega", "ω"), ("Delta", "Δ"), ("Sigma", "Σ"), ("Omega", "Ω"), ("Phi", "Φ"), ("Gamma", "Γ"))}
FUNCIONES = {"sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "exp", "ln", "log", "abs", "min", "max"}
TOK = re.compile(r"\s*(\d+\.?\d*(?:[eE][-+]?\d+)?|[A-Za-z_À-ɏ][A-Za-z0-9_À-ɏ]*|\*\*|[-+*/^=(),<>])")


def _tokens(s):
    out, i = [], 0
    s = s.strip()
    while i < len(s):
        m = TOK.match(s, i)
        if not m:
            i += 1
            continue
        out.append(m.group(1))
        i = m.end()
    return out


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        v = self.peek()
        self.i += 1
        return v

    # igualdad / desigualdad
    def ecuacion(self):
        partes = [self.suma()]
        while self.peek() in ("=", "<", ">"):
            op = self.next()
            partes.append('<span class="m-op"> %s </span>' % html.escape(op))
            partes.append(self.suma())
        return "".join(partes)

    def suma(self):
        r = self.termino()
        while self.peek() in ("+", "-"):
            op = self.next()
            r += '<span class="m-op"> %s </span>' % ("+" if op == "+" else "−") + self.termino()
        return r

    def termino(self):
        """a*b/c*d  ->  fraccion (a·b)/(c·d): el cociente apila todo lo que lo rodea, como se escribe a mano."""
        num = self.producto()
        while self.peek() == "/":
            self.next()
            den = self.producto()
            num = '<span class="m-frac"><span class="m-frn">%s</span><span class="m-frd">%s</span></span>' % (num, den)
        return num

    def producto(self):
        r = self.unario()
        while self.peek() == "*":
            self.next()
            r += '<span class="m-op">·</span>' + self.unario()
        return r

    def unario(self):
        if self.peek() == "-":
            self.next()
            return '<span class="m-op">−</span>' + self.unario()
        if self.peek() == "+":
            self.next()
        return self.potencia()

    def potencia(self):
        base = self.atomo()
        if self.peek() in ("^", "**"):
            self.next()
            if self.peek() == "(":
                self.next()
                e = self.suma()
                if self.peek() == ")":
                    self.next()
            else:
                e = self.atomo_simple()
            base += '<span class="m-sup">%s</span>' % e
        return base

    def atomo_simple(self):
        t = self.next()
        if t == "-":
            return '<span class="m-op">−</span>' + self.atomo_simple()
        return _simbolo(t)

    def atomo(self):
        t = self.peek()
        if t is None:
            return ""
        if t == "(":
            self.next()
            e = self.suma()
            if self.peek() == ")":
                self.next()
            return '<span class="m-paren"><span class="m-pl"></span><span>%s</span><span class="m-pr"></span></span>' % e
        if t == "sqrt" and self.i + 1 < len(self.t) and self.t[self.i + 1] == "(":
            self.next(); self.next()
            e = self.suma()
            if self.peek() == ")":
                self.next()
            return '<span class="m-sqrt"><span class="m-rad">√</span><span class="m-radarg">%s</span></span>' % e
        if t in FUNCIONES and self.i + 1 < len(self.t) and self.t[self.i + 1] == "(":
            self.next()
            return '<span class="m-fn">%s</span>' % html.escape(t) + self.atomo()
        self.next()
        return _simbolo(t)


def _simbolo(t):
    if t is None:
        return ""
    if re.match(r"^\d", t):
        return '<span class="m-num">%s</span>' % html.escape(t)
    base, _, sub = t.partition("_")
    b = GRIEGAS.get(base, base)
    r = '<span class="m-var">%s</span>' % html.escape(b)
    if sub:
        r += '<span class="m-sub">%s</span>' % html.escape(GRIEGAS.get(sub, sub).replace("_", ","))
    return r


def ecuacion_html(expr, etiqueta=""):
    """<div class=ws-eq> con la formula en formato Hekatan LISP; `etiqueta` va a la derecha, estilo libro: «(2.3.4)»."""
    try:
        cuerpo = _P(_tokens(expr)).ecuacion()
    except Exception:
        cuerpo = html.escape(expr)
    eti = '<span class="deq-tag">%s</span>' % html.escape(etiqueta) if etiqueta else ""
    return '<div class="ws-deq"><div class="deq-body ws-eq">%s</div>%s</div>' % (cuerpo, eti)


CSS = """
.ws-deq{display:flex;flex-wrap:wrap;align-items:center;gap:.3em 1.2em;margin:.2em 0}
.ws-deq>.deq-body{flex:0 1 auto;max-width:100%;min-width:0;overflow-x:auto;overflow-y:hidden;padding:.4em 0 .25em}
.ws-deq>.deq-tag{flex:0 0 auto;margin-left:auto;color:var(--mut);font-size:.85em;white-space:nowrap;font-family:'Segoe UI',sans-serif}
.ws-eq{font-family:Georgia,'Times New Roman',Times,serif;font-size:11.5pt}
.m-var{font-style:italic;color:var(--var);font-size:105%}.m-num{color:var(--num)}
.m-op{color:var(--mut);padding:0 .08em}.m-fn{font-style:normal;font-weight:600;color:var(--fg);padding-right:.05em}
.m-frac{display:inline-flex;flex-direction:column;vertical-align:middle;text-align:center;margin:0 .15em;line-height:110%}
.m-frn{border-bottom:1pt solid currentColor;padding:0 .35em .5pt}.m-frd{padding:.5pt .35em 0}
.m-sup{display:inline-block;margin-left:1pt;vertical-align:.55em;line-height:1;font-size:75%}
.m-sub{font-family:Calibri,Candara,Corbel,sans-serif;font-size:80%;vertical-align:-18%;margin-left:1pt}
.m-sqrt{display:inline-flex;align-items:flex-start}.m-rad{font-size:1.05em}.m-radarg{border-top:1.2px solid currentColor;padding:0 .2em;margin-left:-.05em}
.m-paren{display:inline-flex;align-items:stretch;vertical-align:middle}
.m-paren>.m-pl,.m-paren>.m-pr{width:.26em;flex:0 0 auto;border:.075em solid var(--mut);border-radius:50%}
.m-paren>.m-pl{border-right:0;border-top-right-radius:0;border-bottom-right-radius:0;margin-right:.14em}
.m-paren>.m-pr{border-left:0;border-top-left-radius:0;border-bottom-left-radius:0;margin-left:.14em}
"""
