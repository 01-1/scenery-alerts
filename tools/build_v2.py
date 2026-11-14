import sys, math, runpy, json
sys.path.insert(0, __import__('os').path.dirname(__file__))
import flo, track
from flo import Node

SRC, STOPS, OUT, LABEL = sys.argv[1:5]
pts, ch = track.load()

# ---- schedule-based speed (train 42), station chainage km and clock minutes
SCHED = [(0, 7*60+10), (49.43, 7*60+49), (64.29, 8*60), (122.75, 8*60+42), (182.99, 9*60+39),
         (205.71, 9*60+59), (237.43, 10*60+26), (295.87, 11*60+6), (393.34, 12*60+35),
         (420.91, 13*60+2), (449.76, 13*60+21), (526.91, 14*60+5), (554.88, 14*60+37),
         (604.55, 15*60+46), (681.77, 16*60+22), (697.77, 16*60+43)]
DEP = {49.43: 2, 64.29: 1, 122.75: 3, 182.99: 4, 205.71: 2, 237.43: 2, 295.87: 2, 393.34: 10,
       420.91: 1, 449.76: 4, 526.91: 2, 554.88: 40, 604.55: 2, 681.77: 2}

def seg_speed(c):
    km = c / 1000
    for (a, ta), (b, tb) in zip(SCHED, SCHED[1:]):
        if km <= b:
            run = (tb - ta - DEP.get(a, 0)) * 60
            return (b - a) * 1000 / run
    return 15.0

def eta(c):
    km = c / 1000
    for (a, ta), (b, tb) in zip(SCHED, SCHED[1:]):
        if km <= b:
            d = ta + DEP.get(a, 0); return d + (tb - d) * (km - a) / (b - a)
    return SCHED[-1][1]

def enu(p, q):
    k = math.cos(math.radians(p[0]))
    return ((q[1] - p[1]) * k * 111320, (q[0] - p[0]) * 110540)

def side_at(c, target):
    p, a, b = track.at(pts, ch, c), track.at(pts, ch, c - 60), track.at(pts, ch, c + 60)
    dx, dy = enu(a, b); tx, ty = enu(p, target)
    return 'LEFT' if dx * ty - dy * tx > 0 else 'RIGHT'

def inside_at(c):
    a, b, d = track.at(pts, ch, c - 700), track.at(pts, ch, c), track.at(pts, ch, c + 700)
    x1, y1 = enu(a, b); x2, y2 = enu(b, d)
    return 'LEFT' if x1 * y2 - y1 * x2 > 0 else 'RIGHT'

LEAD = {'sec': 75, 'look': 40, 'pre': 150, 'stn': 20}
stops = runpy.run_path(STOPS)['S']
rows, prev = [], -1e9
for s in stops:
    at = s['at']
    if at[0] == 'fixed':
        _, la, lo, r = at
        _, c_lm, _ = track.project(pts, ch, (la, lo))
        rows.append(dict(s, lat=la, lon=lo, r=r, c_lm=c_lm, trig=c_lm, off=0)); continue
    if at[0] == 'km':
        c_lm, off = at[1] * 1000, 0
    else:
        off, c_lm, _ = track.project_first(pts, ch, at, prev - 3000)
    v = seg_speed(c_lm) * 1.25
    lead = min(3000, max(300, LEAD[s['kind']] * v))
    r = min(800, max(400, v * 14))
    trig = c_lm - lead
    la, lo = track.at(pts, ch, trig + r)
    text = s['text']
    if '{side}' in text:
        sd = inside_at(c_lm) if s.get('inside') else side_at(c_lm if s['at'][0] != 'fixed' else c_lm, s['side'])
        text = text.replace('{side}', sd)
    rows.append(dict(s, text=text, lat=la, lon=lo, r=round(r), c_lm=c_lm, trig=trig, off=off))
    prev = c_lm

# fixed points: fill {side}
for row in rows:
    if '{side}' in row['text']:
        row['text'] = row['text'].replace('{side}', side_at(row['c_lm'], row['side']))

# array order = order along the route (by trigger chainage); keep list order for the
# Philadelphia fixed points, whose shape chainage is not their real position
order_ok = all(rows[i]['trig'] <= rows[i + 1]['trig'] + 1 for i in range(len(rows) - 1)
               if rows[i]['at'][0] != 'fixed' and rows[i + 1]['at'][0] != 'fixed')
assert order_ok, [(r['title'], round(r['trig'])) for r in rows]

def stars(n): return '★' * n + '☆' * (5 - n)
for row in rows:
    row['ftitle'] = f"{stars(row['stars'])} {row['title']}"

# ---- edit the original flow graph
version, _, blocks = flo.parse(open(SRC, 'rb').read())
FB, VA, LOC, FE, ED, AS, FK, NT = blocks
assert [b.t for b in blocks] == [1072, 1012, 1089, 1073, 1058, 1011, 1060, 1103]
v_stop, v_index = FE.f[7], FE.f[8]
v_stops = VA.f[5]
NULL = AS.f[6]; NOW = NT.f[24]
assert v_stop.f == ['sceneryStop'] and v_index.f == ['sceneryIndex'] and v_stops.f == ['sceneryStops']
assert NULL.t == 103 and NOW.t == 202
v_acc, v_fix = LOC.f[14], LOC.f[16]
v_lat, v_lon = LOC.f[9], LOC.f[10]
assert (v_acc.f, v_fix.f, v_lat.f, v_lon.f) == (['sceneryAccuracy'], ['sceneryFixTime'], ['sceneryLat'], ['sceneryLon'])
v_skip = Node(102, ['scenerySkip'])

N = lambda x: Node(104, [float(x)]); S = lambda x: Node(106, [x])
AND = lambda a, b: Node(111, [a, b]); CAT = lambda a, b: Node(119, [a, b])
LE = lambda a, b: Node(127, [a, b]); ARR = lambda xs: Node(132, [list(xs)])
NE = lambda a, b: Node(135, [a, b]); IDX = lambda a, b: Node(137, [a, N(b) if isinstance(b, (int, float)) else b])
SUB = lambda a, b: Node(138, [a, b]); NEG = lambda a: Node(131, [a])
DIST = lambda a, b, c, d: Node(311, [a, b, c, d])

def HIT():  # same test as the original flow, minus the null check
    return AND(AND(AND(AND(NE(v_acc, NULL), LE(v_acc, N(500))), NE(v_fix, NULL)),
                   LE(SUB(NOW, v_fix), N(120))),
               LE(DIST(v_lat, v_lon, IDX(v_stop, 0), IDX(v_stop, 1)), IDX(v_stop, 2)))

def SKIPPED():  # first+0.5 <= index <= last-0.5  (scenerySkip = [last, first, hit])
    return AND(LE(SUB(IDX(v_skip, 1), N(-0.5)), v_index), LE(v_index, SUB(IDX(v_skip, 0), N(0.5))))

# condition: stop not done && (hit || skipped)   [hit + skipped >= 0.5]
ED.f[5] = AND(NE(v_stop, NULL), LE(N(0.5), SUB(HIT(), SUB(N(0), SKIPPED()))))

# update block: scenerySkip = [hit ? index : last, (first == -1 && hit) ? index : first, hit]
UPD = Node(1012, [7, 0, 36, AS,
                  ARR([IDX(ARR([IDX(v_skip, 0), v_index]), HIT()),
                       IDX(ARR([IDX(v_skip, 1), v_index]), AND(LE(IDX(v_skip, 1), N(-0.5)), HIT())),
                       HIT()]),
                  v_skip])
ED.f[3] = UPD
INIT = Node(1012, [3, 0, 12, LOC, ARR([N(-1), N(-1), N(0)]), v_skip])
VA.f[3] = INIT

# notification: "Skipped: " prefix and note when not a real hit
NT.f[6] = CAT(IDX(ARR([S('Skipped: '), S('')]), IDX(v_skip, 2)), IDX(v_stop, 3))
NT.f[7] = IDX(ARR([CAT(S('Missed, no GPS fix nearby. '), IDX(v_stop, 4)), IDX(v_stop, 4)]), IDX(v_skip, 2))

# stops array
def stop_node(row):
    return ARR([N(round(row['lat'], 6)), NEG(N(round(-row['lon'], 6))), N(row['r']), S(row['ftitle']), S(row['text'])])
VA.f[4] = ARR([stop_node(r) for r in rows])

# ids and layout
FB.f[4] = LABEL
for blk, (sid, x, y) in zip([FB, VA, INIT, LOC, FE, ED, UPD, AS, FK, NT],
                            [(1, 4, 0), (2, 0, 6), (3, 0, 12), (4, 0, 18), (5, 0, 24), (6, 0, 30),
                             (7, 0, 36), (8, 0, 42), (9, 0, 48), (10, 8, 54)]):
    blk.f[0], blk.f[1], blk.f[2] = sid, x, y
out_blocks = [FB, VA, INIT, LOC, FE, ED, UPD, AS, FK, NT]
data = flo.write(version, 11, out_blocks)
open(OUT, 'wb').write(data)

# verify: re-parse and re-serialize identically
v2, n2, b2 = flo.parse(data)
assert flo.write(v2, n2, b2) == data and len(b2) == 10
print(f'wrote {OUT}: {len(data)} bytes, {len(b2)} blocks, {len(rows)} stops')
json.dump([dict(title=r['ftitle'], kind=r['kind'], km=round(r['c_lm'] / 1000, 1),
                trig_km=round(r['trig'] / 1000, 2), eta=f"{int(eta(r['trig'])//60)}:{int(eta(r['trig'])%60):02d}",
                off=round(r['off']), r=r['r'], lat=round(r['lat'], 5), lon=round(r['lon'], 5), text=r['text'])
           for r in rows], open(OUT + '.json', 'w'), indent=1, ensure_ascii=False)
