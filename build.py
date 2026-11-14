"""Build an Automate scenery-alert flow for one direction of a route.

    python3 build.py pennsylvanian east     # or west; no direction = all directions
    python3 build.py --date 2026-11-15 pennsylvanian    # use the timetable running that day

Reads the route's stop list, snaps each alert onto Amtrak's GTFS track shape, and writes
out/<name>.flo plus a .json sidecar listing every alert with its position and schedule time.
"""
import datetime
import json
import math
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scenery'))
import flo, gtfs, track  # noqa: E402
from flo import Node  # noqa: E402

TEMPLATE = ROOT / 'template' / 'scenery-template.flo'
# seconds of warning before the landmark, per alert kind:
# 'sec' section start, 'look' landmark, 'pre' get-ready, 'stn' station arrival
LEAD = {'sec': 75, 'look': 40, 'pre': 150, 'stn': 20}


def stars(n):
    return '★' * n + '☆' * (5 - n)


def enu(p, q):
    k = math.cos(math.radians(p[0]))
    return ((q[1] - p[1]) * k * 111320, (q[0] - p[0]) * 110540)


class Line:
    """Track shape plus timetable for one train."""

    def __init__(self, route_id, train, day):
        self.info, self.pts, stations = gtfs.trip(route_id, train, day)
        self.ch = track.chain(self.pts)
        self.sched, prev = [], -1e18  # (chainage m, arrival min, departure min)
        for _, la, lo, arr, dep in stations:
            _, c, _ = track.project_first(self.pts, self.ch, (la, lo), prev)
            self.sched.append((c, arr, dep)); prev = c

    def at(self, c):
        return track.at(self.pts, self.ch, c)

    def _seg(self, c):
        for a, b in zip(self.sched, self.sched[1:]):
            if c <= b[0]:
                return a, b
        return self.sched[-2], self.sched[-1]

    def speed(self, c):  # schedule average m/s over the station-to-station run
        (ca, _, da), (cb, ab, _) = self._seg(c)
        return (cb - ca) / ((ab - da) * 60)

    def eta(self, c):
        (ca, _, da), (cb, ab, _) = self._seg(c)
        return da + (ab - da) * min(1, max(0, (c - ca) / (cb - ca)))

    def side(self, c, target):  # which side of the train `target` is on, at chainage c
        p, a, b = self.at(c), self.at(c - 60), self.at(c + 60)
        dx, dy = enu(a, b); tx, ty = enu(p, target)
        return 'LEFT' if dx * ty - dy * tx > 0 else 'RIGHT'

    def inside(self, c):  # inside of the bend at chainage c
        a, b, d = self.at(c - 700), self.at(c), self.at(c + 700)
        x1, y1 = enu(a, b); x2, y2 = enu(b, d)
        return 'LEFT' if x1 * y2 - y1 * x2 > 0 else 'RIGHT'


def place(line, stops):
    """Turn the stop list into alert circles on the track."""
    rows, prev = [], -1e18
    for s in stops:
        at = s['at']
        if at[0] == 'fixed':  # off the GTFS shape (Philadelphia 30th St detour): use as given
            _, la, lo, r = at
            _, c_lm, _ = track.project(line.pts, line.ch, (la, lo))
            rows.append(dict(s, lat=la, lon=lo, r=r, c_lm=c_lm, trig=c_lm, off=0, fixed=True))
            continue
        if at[0] == 'km':
            c_lm, off = at[1] * 1000, 0
        else:
            off, c_lm, _ = track.project_first(line.pts, line.ch, at, prev - 3000)
        v = line.speed(c_lm) * 1.25  # trains run faster than the schedule average between stops
        lead = min(3000, max(300, LEAD[s['kind']] * v))
        r = min(800, max(400, v * 14))
        trig = c_lm - lead
        la, lo = line.at(trig + r)  # circle edge sits on the trigger point
        rows.append(dict(s, lat=la, lon=lo, r=round(r), c_lm=c_lm, trig=trig, off=off, fixed=False))
        prev = c_lm
    for row in rows:
        if '{side}' in row['text']:
            sd = line.inside(row['c_lm']) if row.get('inside') else line.side(row['c_lm'], row['side'])
            row['text'] = row['text'].replace('{side}', sd)
        row['ftitle'] = f"{stars(row['stars'])} {row['title']}"
    return rows


def check(line, rows):
    """Ride the track: every circle must be first entered at its trigger point, in list order."""
    step, first = 10.0, {}
    c = 0.0
    while c <= line.ch[-1]:
        p = line.at(c)
        for i, row in enumerate(rows):
            if i not in first and track.hav(p, (row['lat'], row['lon'])) <= row['r']:
                first[i] = c
        c += step
    seq = [i for i in sorted(first, key=first.get) if not rows[i]['fixed']]
    plain = [i for i, r in enumerate(rows) if not r['fixed']]
    assert seq == plain, ('entry order', [rows[i]['title'] for i in seq])
    early = {}
    for i in plain:  # on curves the circle edge is a little before the trigger point
        d = rows[i]['trig'] - first[i]
        assert -2 * step <= d <= 150, ('entry not at trigger', rows[i]['title'], first[i], rows[i]['trig'])
        early[rows[i]['title']] = d
    worst = max(early, key=early.get)
    return worst, round(early[worst]), {rows[i]['title']: round(first[i] / 1000, 2) for i in first if rows[i]['fixed']}


def build_flow(rows, label):
    version, _, blocks = flo.parse(TEMPLATE.read_bytes())
    FB, VA, LOC, FE, ED, AS, FK, NT = blocks
    assert [b.t for b in blocks] == [1072, 1012, 1089, 1073, 1058, 1011, 1060, 1103]
    v_stop, v_index, v_stops = FE.f[7], FE.f[8], VA.f[5]
    NULL, NOW = AS.f[6], NT.f[24]
    assert v_stop.f == ['sceneryStop'] and v_index.f == ['sceneryIndex'] and v_stops.f == ['sceneryStops']
    assert NULL.t == 103 and NOW.t == 202
    v_acc, v_fix, v_lat, v_lon = LOC.f[14], LOC.f[16], LOC.f[9], LOC.f[10]
    assert (v_acc.f, v_fix.f, v_lat.f, v_lon.f) == (['sceneryAccuracy'], ['sceneryFixTime'], ['sceneryLat'], ['sceneryLon'])
    v_skip = Node(102, ['scenerySkip'])  # [last hit index, first hit index, this one is a real hit]

    N = lambda x: Node(104, [float(x)]); S = lambda x: Node(106, [x])
    AND = lambda a, b: Node(111, [a, b]); CAT = lambda a, b: Node(119, [a, b])
    LE = lambda a, b: Node(127, [a, b]); ARR = lambda xs: Node(132, [list(xs)])
    NE = lambda a, b: Node(135, [a, b]); IDX = lambda a, b: Node(137, [a, N(b) if isinstance(b, (int, float)) else b])
    SUB = lambda a, b: Node(138, [a, b]); NEG = lambda a: Node(131, [a])
    DIST = lambda a, b, c, d: Node(311, [a, b, c, d])

    def HIT():  # fresh, accurate GPS fix inside this stop's circle (the template's test)
        return AND(AND(AND(AND(NE(v_acc, NULL), LE(v_acc, N(500))), NE(v_fix, NULL)),
                       LE(SUB(NOW, v_fix), N(120))),
                   LE(DIST(v_lat, v_lon, IDX(v_stop, 0), IDX(v_stop, 1)), IDX(v_stop, 2)))

    def SKIPPED():  # first < index < last: passed without a hit, after alerts started
        return AND(LE(SUB(IDX(v_skip, 1), N(-0.5)), v_index), LE(v_index, SUB(IDX(v_skip, 0), N(0.5))))

    # notify when the stop is pending and (hit or skipped)   [hit + skipped >= 0.5]
    ED.f[5] = AND(NE(v_stop, NULL), LE(N(0.5), SUB(HIT(), SUB(N(0), SKIPPED()))))
    UPD = Node(1012, [7, 0, 36, AS,
                      ARR([IDX(ARR([IDX(v_skip, 0), v_index]), HIT()),
                           IDX(ARR([IDX(v_skip, 1), v_index]), AND(LE(IDX(v_skip, 1), N(-0.5)), HIT())),
                           HIT()]),
                      v_skip])
    ED.f[3] = UPD
    INIT = Node(1012, [3, 0, 12, LOC, ARR([N(-1), N(-1), N(0)]), v_skip])
    VA.f[3] = INIT
    NT.f[6] = CAT(IDX(ARR([S('Skipped: '), S('')]), IDX(v_skip, 2)), IDX(v_stop, 3))
    NT.f[7] = IDX(ARR([CAT(S('Missed, no GPS fix nearby. '), IDX(v_stop, 4)), IDX(v_stop, 4)]), IDX(v_skip, 2))

    VA.f[4] = ARR([ARR([N(round(r['lat'], 6)), NEG(N(round(-r['lon'], 6))), N(r['r']), S(r['ftitle']), S(r['text'])])
                   for r in rows])
    FB.f[4] = label
    order = [FB, VA, INIT, LOC, FE, ED, UPD, AS, FK, NT]
    for sid, blk in enumerate(order, 1):
        blk.f[0], blk.f[1], blk.f[2] = sid, (8 if blk is NT else 4 if blk is FB else 0), 6 * (sid - 1)
    data = flo.write(version, len(order) + 1, order)
    v2, n2, b2 = flo.parse(data)
    assert flo.write(v2, n2, b2) == data and len(b2) == len(order)
    return data


def build(route, direction, day=None):
    rdir = ROOT / 'routes' / route
    cfg = runpy.run_path(str(rdir / 'route.py'))
    d = cfg['DIRECTIONS'][direction]
    day = day or datetime.date.fromisoformat(cfg['TIMETABLE_DATE'])
    line = Line(cfg['ROUTE_ID'], d['train'], day)
    rows = place(line, runpy.run_path(str(rdir / d['stops']))['S'])
    worst, early, fixed = check(line, rows)
    out = ROOT / 'out' / d['out']
    out.parent.mkdir(exist_ok=True)
    data = build_flow(rows, d['label'])
    out.write_bytes(data)
    hm = lambda m: f'{int(m // 60)}:{int(m % 60):02d}'
    json.dump(dict(line.info, alerts=[
        dict(title=r['ftitle'], kind=r['kind'], km=round(r['c_lm'] / 1000, 1),
             trig_km=round(r['trig'] / 1000, 2), eta=hm(line.eta(r['trig'])), off=round(r['off']),
             r=r['r'], lat=round(r['lat'], 5), lon=round(r['lon'], 5), text=r['text'])
        for r in rows]), open(str(out) + '.json', 'w'), indent=1, ensure_ascii=False)
    i = line.info
    print(f"{out.name}: {len(data)} bytes, 10 blocks, {len(rows)} alerts; "
          f"train {i['train']} departing {i['departs']}, timetable {i['timetable']}")
    print(f'  every circle first entered at its trigger, in order; earliest: {worst} {early} m early')
    print(f'  off-shape circles (km where the GTFS shape first enters them): {fixed}')


if __name__ == '__main__':
    args, day = sys.argv[1:], None
    if args[0] == '--date':
        day = datetime.date.fromisoformat(args[1]); args = args[2:]
    route = args[0]
    dirs = args[1:] or list(runpy.run_path(str(ROOT / 'routes' / route / 'route.py'))['DIRECTIONS'])
    for dn in dirs:
        build(route, dn, day)
