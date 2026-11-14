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


def trip(route_id, train):
    """First trip of `train` (the public train number) on `route_id`.

    Returns (shape points [(lat, lon)], stops [(stop_id, lat, lon, arr_min, dep_min)]).
    """
    z = feed()
    t = next(r for r in rows(z, 'trips.txt')
             if r['route_id'] == route_id and r['trip_short_name'] == str(train))
    pts = sorted(((int(r['shape_pt_sequence']), float(r['shape_pt_lat']), float(r['shape_pt_lon']))
                  for r in rows(z, 'shapes.txt') if r['shape_id'] == t['shape_id']))
    where = {r['stop_id']: (float(r['stop_lat']), float(r['stop_lon'])) for r in rows(z, 'stops.txt')}
    st = sorted((int(r['stop_sequence']), r['stop_id'], minutes(r['arrival_time']), minutes(r['departure_time']))
                for r in rows(z, 'stop_times.txt') if r['trip_id'] == t['trip_id'])
    return [(la, lo) for _, la, lo in pts], [(s, *where[s], a, d) for _, s, a, d in st]
