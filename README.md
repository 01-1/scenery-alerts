# Scenery alerts for train rides

Flows for [Automate](https://llamalab.com/automate/) (Android) that pop up a notification shortly
before each scenic spot on a train ride: which side to look, what you're seeing, and a 1-5 star
rating of how worth it it is. They use only GPS, so they work with no mobile data, and each flow is
10 blocks, which fits Automate's free tier.

## Ready-made flows

| File | Trip | Alerts |
|---|---|---|
| [`Pennsylvanian Westbound v2 NYC-PGH.flo`](out/Pennsylvanian%20Westbound%20v2%20NYC-PGH.flo) | Amtrak Pennsylvanian, New York to Pittsburgh (train 43) | 66 |
| [`Pennsylvanian Eastbound v2 PGH-NYC.flo`](out/Pennsylvanian%20Eastbound%20v2%20PGH-NYC.flo) | Amtrak Pennsylvanian, Pittsburgh to New York (train 42) | 65 |

Copy the `.flo` to your phone, import it in Automate, and tap its start button ("Start westbound
scenery alerts v2" / "Start eastbound scenery alerts v2"). Allow location and notifications.
Each `.flo` has a `.json` beside it listing every alert with its position, scheduled time and text.

Highlights: the Manhattan skyline, Rockville Bridge, the Statue of Liberty in the Susquehanna,
Horseshoe Curve and the Conemaugh Gap.

Alerts are triggered by GPS, not the clock, so a flow works on any train that runs on that track.
Only the warning distances depend on the timetable's speeds. The committed flows use Amtrak's
timetable that starts 2026-11-18, which runs two trains each way:

| Train | Leaves | Mountains (Altoona) |
|---|---|---|
| 42 east | Pittsburgh 7:10 | about 9:40 |
| 44 east | Pittsburgh 13:00 | about 15:30 |
| 43 west | New York 5:50 | about 12:20 |
| 45 west | New York 12:25 | about 19:00, after dark |

## How the flow behaves

- On every GPS fix it checks every alert that hasn't fired yet, so a missed spot never blocks later ones.
- An alert fires when a fresh fix (under 2 minutes old, accuracy under 500 m) falls inside its circle.
  Circles are placed on the track so the train enters them 20-150 s before the sight, depending on
  the alert type and the train's speed there.
- Once the first alert has fired, any earlier alert the train passed without a GPS hit shows up as
  "Skipped: ..." with its text. Alerts before the first hit stay silent, so you can start the flow mid-trip.
- LEFT/RIGHT is worked out from the direction of travel at each spot.

## Building

```
python3 build.py pennsylvanian          # both directions
python3 build.py pennsylvanian west     # one direction
```

The first run downloads [Amtrak's GTFS feed](https://content.amtrak.com/content/gtfs/GTFS.zip)
into `data/` (git-ignored) and reuses the cached zip on later runs. The build reads
the track shape and timetable, snaps the alerts onto the track, checks their trigger
points and order, and writes the flows to `out/`.

The build uses `TIMETABLE_DATE` in `routes/<route>/route.py` by default. To choose a date,
run `python3 build.py --date YYYY-MM-DD pennsylvanian` with your travel date. If that
train has no service on the selected date, the builder uses the next timetable in
the feed or fails if there is none. Check the selected departure and timetable in
the build output or the `.json` sidecar.

- `routes/<route>/route.py`: GTFS route id, train number per direction, flow label and file name.
- `routes/<route>/stops_*.py`: the alerts in travel order. Each has a kind (`sec` section start,
  `look` landmark, `pre` get-ready, `stn` station), a position, a star rating, a title and text.
  `{side}` in the text is replaced by LEFT or RIGHT.
- `template/scenery-template.flo`: the 8-block flow that the builder adds alerts, ratings,
  and skip logic to.
- `scenery/flo.py`: reader and writer for Automate's `.flo` format. It round-trips the template
  byte for byte.
- `tools/matrix_send.py`: optional, sends built files to a Matrix room.

Format reference: [stevendejongnl/automate-flo](https://github.com/stevendejongnl/automate-flo).

## Known limits

- Amtrak's track shape skips the loop into Philadelphia 30th Street, so the 30th Street and
  Schuylkill alerts use fixed circles instead of track-snapped ones.
- GPS drops out in tunnels (Hudson, Gallitzin, Spruce Creek), and fixes can lag after them.
- The skip logic assumes Automate treats true/false as 1/0 in arithmetic.

## License

MIT, see [LICENSE](LICENSE).
