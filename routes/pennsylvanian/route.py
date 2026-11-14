# Amtrak Pennsylvanian, New York - Philadelphia - Harrisburg - Pittsburgh.
# Track shape and timetable come from Amtrak's GTFS feed (route 64).
ROUTE_ID = '64'
DIRECTIONS = {
    'east': dict(train=42, stops='stops_east.py', label='Start eastbound scenery alerts v2',
                 out='Pennsylvanian Eastbound v2 PGH-NYC.flo'),
    'west': dict(train=43, stops='stops_west.py', label='Start westbound scenery alerts v2',
                 out='Pennsylvanian Westbound v2 NYC-PGH.flo'),
}
