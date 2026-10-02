"""KiCad 8 sematik yazici (stdlib). Semboller sistem kutuphanelerinden okunur, extends
duzlestirilir ve .kicad_sch icine gomulur. Pin konumlari sembol donusumuyle hesaplanir."""
import os, uuid, math
import sexp
from sexp import Sym, find, find_all

SYM_DIRS = [os.environ.get('KICAD8_SYMBOL_DIR', ''), '/usr/share/kicad/symbols',
            '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols']
UUID_NS = uuid.UUID('6f3c1a52-7d0e-4c55-9a4b-6b1d2f0e8a11')

def uid(*parts):
    """Deterministik UUID: ayni girdi -> ayni dosya (git diff temiz kalir)."""
    return str(uuid.uuid5(UUID_NS, '/'.join(str(p) for p in parts)))

def r4(v):
    return round(v + 0.0, 4)

class SymbolLibs:
    def __init__(self, extra=None):
        self.cache = {}
        self.extra = extra or {}          # 'MagPanel' -> dosya yolu

    def _lib(self, name):
        if name not in self.cache:
            path = self.extra.get(name)
            if not path:
                for d in SYM_DIRS:
                    if d and os.path.exists(os.path.join(d, name + '.kicad_sym')):
                        path = os.path.join(d, name + '.kicad_sym'); break
            if not path:
                raise FileNotFoundError('sembol kutuphanesi yok: ' + name)
            self.cache[name] = sexp.parse(open(path, encoding='utf-8').read())
        return self.cache[name]

    def raw(self, lib, name):
        for e in self._lib(lib):
            if isinstance(e, list) and e[:1] == ['symbol'] and e[1] == name:
                return e
        raise KeyError('%s:%s' % (lib, name))

    def flat(self, lib_id):
        """lib_id 'Lib:Name' -> sematige gomulecek duzlestirilmis sembol (adi 'Lib:Name')."""
        lib, name = lib_id.split(':', 1)
        s = self.raw(lib, name)
        ext = find(s, 'extends')
        if ext:
            parent = self.flat(lib + ':' + ext[1])
            pname = ext[1]
            out = [Sym('symbol'), lib_id]
            child_props = {p[1]: p for p in find_all(s, 'property')}
            for e in parent[2:]:
                if isinstance(e, list) and e and e[0] == 'property' and e[1] in child_props:
                    out.append(child_props.pop(e[1]))
                elif isinstance(e, list) and e and e[0] == 'symbol':
                    sub = list(e); sub[1] = name + sub[1][len(pname):]
                    out.append(sub)
                else:
                    out.append(e)
            # ebeveynde olmayan cocuk ozellikleri
            idx = max(i for i, e in enumerate(out) if isinstance(e, list) and e and e[0] == 'property')
            for p in child_props.values():
                idx += 1; out.insert(idx, p)
            return out
        out = list(s); out[1] = lib_id
        return out

    def pins(self, lib_id):
        """{numara: dict(name, type, x, y, ang, length, unit)} (kutuphane koordinatlari, y yukari)."""
        res = {}
        def walk(x, unit):
            for e in x:
                if isinstance(e, list) and e:
                    if e[0] == 'symbol':
                        parts = e[1].rsplit('_', 2)
                        walk(e, int(parts[-2]) if len(parts) == 3 and parts[-2].isdigit() else unit)
                    elif e[0] == 'pin':
                        at = find(e, 'at'); nu = find(e, 'number'); nm = find(e, 'name'); ln = find(e, 'length')
                        res[str(nu[1])] = dict(name=nm[1], type=str(e[1]), x=at[1], y=at[2],
                                               ang=at[3] if len(at) > 3 else 0, length=ln[1], unit=unit)
        walk(self.flat(lib_id), 0)
        return res

def _rot_mirror(x, y, rot, mirror):
    """KiCad sirasi (kicad-cli netlist ile dogrulandi): once donus (CCW), sonra ayna."""
    a = math.radians(rot)
    rx = x * math.cos(a) - y * math.sin(a)
    ry = x * math.sin(a) + y * math.cos(a)
    if mirror == 'y':
        rx = -rx
    elif mirror == 'x':
        ry = -ry
    return rx, ry

def xform(px, py, at, rot, mirror):
    """Kutuphane noktasi (y yukari) -> sematik (y asagi)."""
    rx, ry = _rot_mirror(px, py, rot, mirror)
    return (r4(at[0] + rx), r4(at[1] - ry))

def dir_vec(ang, rot, mirror):
    """Pin yonu (baglanti noktasindan govdeye) -> sematik birim vektor."""
    rx, ry = _rot_mirror(math.cos(math.radians(ang)), math.sin(math.radians(ang)), rot, mirror)
    return (round(rx), round(-ry))
