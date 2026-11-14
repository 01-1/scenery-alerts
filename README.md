# Scenery alerts for train rides

Flows for [Automate](https://llamalab.com/automate/) (Android) that pop up a notification shortly
before each scenic spot on a train ride: which side to look, what you're seeing, and a 1-5 star
rating of how worth it it is. They use only GPS, so they work with no mobile data, and each flow is
10 blocks, which fits Automate's free tier.

## Ready-made flows

| File | Trip | Alerts |
|---|---|---|
| [`out/Pennsylvanian Westbound v2 NYC-PGH.flo`](out/) | Amtrak Pennsylvanian, New York to Pittsburgh (train 43) | 66 |
| [`out/Pennsylvanian Eastbound v2 PGH-NYC.flo`](out/) | Amtrak Pennsylvanian, Pittsburgh to New York (train 42) | 65 |

Copy the `.flo` to your phone, import it in Automate, and tap its start button ("Start westbound
scenery alerts v2" / "Start eastbound scenery alerts v2"). Allow location and notifications.
Each `.flo` has a `.json` beside it listing every alert with its position, scheduled time and text.

Highlights: the Manhattan skyline, Rockville Bridge, the Statue of Liberty in the Susquehanna,
Horseshoe Curve and the Conemaugh Gap. The flows also work on the other daily trains (44 east,
45 west), which use the same track. In GTFS, train 43 leaves New York at 5:50, so the skyline may be
only lights in winter, but it crosses the mountains around midday. Train 45 crosses them after dark.

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
into `data/` (git-ignored). The build reads the train's track shape and timetable from it, snaps each
alert onto the track, checks that a ride along the track enters every circle at its trigger point and
in list order, and writes `out/`.

- `routes/<route>/route.py`: GTFS route id, train number per direction, flow label and file name.
- `routes/<route>/stops_*.py`: the alerts in travel order. Each has a kind (`sec` section start,
  `look` landmark, `pre` get-ready, `stn` station), a position, a star rating, a title and text.
  `{side}` in the text is replaced by LEFT or RIGHT.
- `template/scenery-template.flo`: the 8-block flow the builder edits (made with Codex). The builder
  adds the skip and rating logic and swaps in the alert list.
- `scenery/flo.py`: reader and writer for Automate's `.flo` format. It round-trips the template
  byte for byte.
- `tools/matrix_send.py`: optional, sends built files to a Matrix room.

Format reference: [stevendejongnl/automate-flo](https://github.com/stevendejongnl/automate-flo).
Block and operator ids not listed there were worked out from the template.

## Known limits

- Amtrak's track shape skips the loop into Philadelphia 30th Street, so the 30th Street and
  Schuylkill alerts use fixed circles instead of track-snapped ones.
- GPS drops out in tunnels (Hudson, Gallitzin, Spruce Creek), and fixes can lag after them.
- The skip logic assumes Automate treats true/false as 1/0 in arithmetic.
