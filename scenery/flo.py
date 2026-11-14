"""Minimal Automate .flo reader/writer for the scenery-alert flow.

Layouts for 1012/1058/1072/1103 and expression literals follow
github.com/stevendejongnl/automate-flo; layouts for 1011, 1060, 1073, 1089
and expression operators were inferred from the original scenery flow and
are validated by byte-exact round-trip of that file.
"""
import struct

# field kinds: 'o' object, 's' svarint, 'u' utf, 'b' raw byte, 'd' raw double,
# 'n' uvarint count + that many objects, 'r<k>' raw k bytes
COMMON = ['s', 's', 's']  # stmt id, cellX, cellY
LAYOUT = {
    1072: COMMON + ['o', 'u', 'b', 'b', 'o', 'o'],  # FlowBeginning
    1012: COMMON + ['o', 'o', 'o'],                 # VariableAssign: next, value, var
    1089: COMMON + ['o', 'o', 'o'] + ['o'] * 12,    # Location (gps): pos, neg, continuity, ...
    1073: COMMON + ['o', 'o', 'o', 'o', 'o', 'o'],  # ForEach: done, body, container, ?, value var, index var
    1058: COMMON + ['o', 'o', 'o'],                 # ExpressionDecision: yes, no, expr
    1011: COMMON + ['o', 'o', 'o', 'o'],            # ArraySet: next, index, array var, value
    1060: COMMON + ['o', 'o', 'r3'],                # Fork: parent next, child, 3 raw bytes
    1103: COMMON + ['o', 'o', 'o'] + ['o'] * 21,    # NotificationShow
    16: ['s'],        # boxed Integer
    102: ['u'],       # variable
    103: [],          # null
    104: ['d'],       # number
    106: ['u'],       # string
    111: ['o', 'o'],  # &&
    119: ['o', 'o'],  # string concat
    127: ['o', 'o'],  # <=
    131: ['o'],       # unary minus
    132: ['n'],       # array literal
    135: ['o', 'o'],  # !=
    137: ['o', 'o'],  # subscript
    138: ['o', 'o'],  # minus
    202: [],          # now
    311: ['o', 'o', 'o', 'o'],  # geo distance(lat1, lon1, lat2, lon2)
}


class Node:
    __slots__ = ('t', 'f')

    def __init__(self, t, f=None):
        self.t, self.f = t, list(f or [])

    def __repr__(self):
        return f'N{self.t}{self.f!r}'


class R:
    def __init__(self, d):
        self.d, self.i, self.seen = d, 0, []

    def uv(self):
        r = s = 0
        while True:
            b = self.d[self.i]; self.i += 1
            r |= (b & 0x7f) << s; s += 7
            if b < 0x80:
                return r

    def sv(self):
        n = self.uv()
        return (n >> 1) ^ -(n & 1)

    def utf(self):
        n = self.uv(); s = self.d[self.i:self.i + n]; self.i += n
        return s.decode('utf-8')

    def obj(self):
        t = self.sv()
        if t == 0:
            return None
        if t < 0:
            return self.seen[-t - 1]
        if t not in LAYOUT:
            raise ValueError(f'unknown type {t} at {self.i}')
        n = Node(t); self.seen.append(n)
        for k in LAYOUT[t]:
            if k == 'o': n.f.append(self.obj())
            elif k == 's': n.f.append(self.sv())
            elif k == 'u': n.f.append(self.utf())
            elif k == 'b': n.f.append(self.d[self.i]); self.i += 1
            elif k == 'd': n.f.append(struct.unpack('>d', self.d[self.i:self.i + 8])[0]); self.i += 8
            elif k == 'n':
                c = self.uv(); n.f.append([self.obj() for _ in range(c)])
            elif k[0] == 'r':
                m = int(k[1:]); n.f.append(self.d[self.i:self.i + m]); self.i += m
        return n


def parse(d):
    assert d[:4] == b'LAFl'
    r = R(d); r.i = 6
    version = struct.unpack('>h', d[4:6])[0]
    next_id = r.sv(); cnt = r.uv()
    blocks = [r.obj() for _ in range(cnt)]
    assert r.i == len(d), f'trailing {len(d) - r.i} bytes'
    return version, next_id, blocks


class W:
    def __init__(self):
        self.b = bytearray(); self.seen = {}

    def uv(self, n):
        while True:
            x = n & 0x7f; n >>= 7
            if n: self.b.append(x | 0x80)
            else: self.b.append(x); return

    def sv(self, n):
        self.uv((n << 1) ^ (n >> 63))

    def utf(self, s):
        e = s.encode('utf-8'); self.uv(len(e)); self.b += e

    def obj(self, n):
        if n is None:
            self.sv(0); return
        if id(n) in self.seen:
            self.sv(-(self.seen[id(n)] + 1)); return
        self.seen[id(n)] = len(self.seen)
        self.sv(n.t)
        for k, v in zip(LAYOUT[n.t], n.f, strict=True):
            if k == 'o': self.obj(v)
            elif k == 's': self.sv(v)
            elif k == 'u': self.utf(v)
            elif k == 'b': self.b.append(v)
            elif k == 'd': self.b += struct.pack('>d', v)
            elif k == 'n':
                self.uv(len(v))
                for x in v: self.obj(x)
            elif k[0] == 'r':
                assert len(v) == int(k[1:]); self.b += v


def write(version, next_id, blocks):
    w = W(); w.b += b'LAFl' + struct.pack('>h', version)
    w.sv(next_id); w.uv(len(blocks))
    for b in blocks:
        w.obj(b)
    return bytes(w.b)


def dump(n, depth=0, seen=None):
    seen = set() if seen is None else seen
    pad = '  ' * depth
    if n is None:
        return pad + 'null'
    if id(n) in seen:
        return pad + f'<ref {n.t} id={n.f[0] if n.t > 1000 else "?"}>'
    seen.add(id(n))
    head = f'{pad}{n.t}'
    lines = []
    for k, v in zip(LAYOUT[n.t], n.f):
        if k == 'o': lines.append(dump(v, depth + 1, seen))
        elif k == 'n': lines.append(f'{pad}  [array x{len(v)}]')
        else: lines.append(f'{pad}  {v!r}'[:120])
    return head + '\n' + '\n'.join(lines)
