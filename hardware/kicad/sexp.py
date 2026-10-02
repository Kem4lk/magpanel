"""Kucuk S-ifadesi (KiCad dosya formati) ayristirici / yazici - sadece stdlib.

KiCad .kicad_sym / .kicad_sch / .kicad_mod dosyalari S-ifadesidir. Ayristirici her
listeyi Python list'e, her atomu Sym (ciplak sembol) ya da str (tirnakli metin) ya da
sayiya cevirir; yazici ayni yapiyi KiCad'in okuyacagi bicimde geri yazar.
"""
import re

class Sym(str):
    """Tirnaksiz atom (ornek: symbol, at, yes, hide, passive)."""
    __slots__ = ()

_TOKEN = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))')

def parse(text):
    """Metni ayristir; ust duzey tek ifadeyi dondur."""
    stack = [[]]
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOKEN.match(text, pos)
        if not m:
            if text[pos:].strip() == '':
                break
            raise ValueError('ayristirma hatasi @%d: %r' % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            stack.append([])
        elif m.group(2):
            lst = stack.pop()
            stack[-1].append(lst)
        elif m.group(3) is not None:
            stack[-1].append(m.group(3).replace('\\"', '"').replace('\\n', '\n').replace('\\\\', '\\'))
        else:
            a = m.group(4)
            try:
                v = int(a) if re.fullmatch(r'-?\d+', a) else float(a) if re.fullmatch(r'-?\d*\.\d+(e-?\d+)?|-?\d+e-?\d+', a) else Sym(a)
            except ValueError:
                v = Sym(a)
            stack[-1].append(v)
    if len(stack) != 1 or len(stack[0]) != 1:
        raise ValueError('dengesiz parantez')
    return stack[0][0]

def fmt_num(v):
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, int):
        return str(v)
    s = ('%.6f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def q(s):
    s = str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    return '"' + s + '"'

def dumps(x, indent=0):
    """KiCad stili: kisa listeler tek satir, uzunlar alt satirlara."""
    if not isinstance(x, list):
        if isinstance(x, Sym):
            return str(x)
        if isinstance(x, str):
            return q(x)
        return fmt_num(x)
    if not x:
        return '()'
    flat = [dumps(e, 0) for e in x]
    one = '(' + ' '.join(flat) + ')'
    if not any(isinstance(e, list) for e in x) or (len(one) < 90 and sum(isinstance(e, list) for e in x) <= 2 and '\n' not in one):
        return one
    tab = '\t' * (indent + 1)
    head = []
    rest = []
    for e in x:
        (rest if (rest or isinstance(e, list)) else head).append(e)
    s = '(' + ' '.join(dumps(e, 0) for e in head)
    for e in rest:
        s += '\n' + tab + dumps(e, indent + 1)
    s += '\n' + '\t' * indent + ')'
    return s

# ---- yardimcilar ----
def find(lst, key):
    """Ilk (key ...) alt listesini dondur."""
    for e in lst:
        if isinstance(e, list) and e and e[0] == key:
            return e
    return None

def find_all(lst, key):
    return [e for e in lst if isinstance(e, list) and e and e[0] == key]

def S(*items):
    """Liste kurucu: dize atomlari Sym'e cevirilir ('"..."' ile baslayanlar metin kalir)."""
    out = []
    for it in items:
        if isinstance(it, str) and not isinstance(it, Sym):
            out.append(Sym(it))
        else:
            out.append(it)
    return out
