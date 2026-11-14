"""Read a route's track shape and timetable from Amtrak's public GTFS feed.

The feed is downloaded once into data/ (git-ignored) and read straight from the zip.
"""
import csv
import io
import urllib.request
import zipfile
from pathlib import Path

URL = 'https://content.amtrak.com/content/gtfs/GTFS.zip'
DATA = Path(__file__).resolve().parent.parent / 'data'
ZIP = DATA / 'amtrak-gtfs.zip'


def feed():
    if not ZIP.exists():
        DATA.mkdir(exist_ok=True)
        req = urllib.request.Request(URL, headers={'User-Agent': 'scenery-alerts/1.0'})
        with urllib.request.urlopen(req, timeout=300) as r:
            ZIP.write_bytes(r.read())
    return zipfile.ZipFile(ZIP)


def rows(z, name):
    with z.open(name) as f:
        yield from csv.DictReader(io.TextIOWrapper(f, 'utf-8-sig'))


def minutes(hms):
    h, m, s = map(int, hms.split(':'))
    return h * 60 + m + s / 60


def runs_on(svc, day):
    wd = ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')[day.weekday()]
    return svc['start_date'] <= day.strftime('%Y%m%d') <= svc['end_date'] and svc[wd] == '1'


def trip(route_id, train, day):
    """The trip of `train` (the public train number) on `route_id` that runs on `day`,
    or else the next timetable to start after it.

    Returns (info, shape points [(lat, lon)], stops [(stop_id, lat, lon, arr_min, dep_min)]).
    """
    z = feed()
    cal = {r['service_id']: r for r in rows(z, 'calendar.txt')}
    trips = [r for r in rows(z, 'trips.txt') if r['route_id'] == route_id and r['trip_short_name'] == str(train)]
    today = [r for r in trips if runs_on(cal[r['service_id']], day)]
    later = sorted((r for r in trips if cal[r['service_id']]['start_date'] > day.strftime('%Y%m%d')),
                   key=lambda r: cal[r['service_id']]['start_date'])
    t = (today or later or [None])[0]
    if t is None:
        raise SystemExit(f'train {train} does not run on or after {day}')
    svc = cal[t['service_id']]
    info = dict(train=str(train), trip=t['trip_id'], timetable=f"{svc['start_date']}-{svc['end_date']}")
    pts = sorted(((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon']))
                  for r in rows(z, 'shapes.txt') if r['shape_id'] == t['shape_id']))
    where = {r['stop_id']: (float(r['stop_lat']), float(r['stop_lon'])) for r in rows(z, 'stops.txt')}
    st = sorted((int(r['stop_sequence']), r['stop_id'], minutes(r['arrival_time']), minutes(r['departure_time']))
                for r in rows(z, 'stop_times.txt') if r['trip_id'] == t['trip_id'])
    info['departs'] = f'{int(st[0][3] // 60)}:{int(st[0][3] % 60):02d}'
    return info, [(la, lo) for _, la, lo in pts], [(s, *where[s], a, d) for _, s, a, d in st]
