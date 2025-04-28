import datetime
import utm
import os
import re
import concurrent.futures
import pandas as pd
from tqdm import tqdm
import numpy as np
import matplotlib.pyplot as plt

from aerofiles import igc
from shortest_path.shortest_path import Path, GridSearchShortestPath, Point2f, ShortestPathOptimizer

from shortest_path.task_loader import load_from_xctsk
from pilot_progression.analyze_pilot_progression import canonical_name

'''
This script computs the pilot prorgress towards goal. It is based on the shorts path algorihtm and gradually deletes turnpoints
if it matches them. (Quick and easy)
'''

VERBOSE = True

#def clean_name(name):
#    name = name.lower()
#    name = name.replace("ä", "a").replace("ö", "o").replace("ü", "u").replace('é', 'e').replace('è', 'e').replace('à', 'a')
#    name = re.sub('[^a-zA-Z0-9]+', '-', name)
#    name = name.strip('-')
#    return name

def process_pilot(pilot_item):
    pilot, igc_file = pilot_item

    # restore original task and path (hackedihackhack)
    task = original_task.copy()
    path = original_path.copy()

    #if pilot == 'adrian-muller' or pilot == 'muhlemann-ren':
    #    print('skip', pilot)
    #    continue

    # Compute the pilots progress at each timestep
    with open(igc_file, 'r') as f:
        pilot_igc = igc.Reader().read(f)

    # Detect possible landing
    landing_time = None
    col_time = []
    col_x = []
    col_y = []
    col_gps_alt = []
    for record in pilot_igc['fix_records'][1]:
        
        # TODO: detect landings before airstart..
        if task.airstart > record['time']:
            continue # skip stuff before airstarts

        x, y, _, _ = utm.from_latlon(record['lat'], record['lon'])

        # use dummy date for diff
        #dtime = datetime.datetime.combine(datetime.date.min, record['time'])

        col_time.append(record['time'])
        col_x.append(x)
        col_y.append(y)
        col_gps_alt.append(record['gps_alt'])

    df_landing = pd.DataFrame({
        'time': col_time,
        'utm_x': col_x,
        'utm_y': col_y,
        'gps_alt': col_gps_alt,
    })

    # Compute deltas
    df_landing['time_sec'] = df_landing['time'].apply(
        lambda t: t.hour * 3600 + t.minute * 60 + t.second
    )
    df_landing['dx'] = df_landing['utm_x'].diff()
    df_landing['dy'] = df_landing['utm_y'].diff()
    df_landing['dt'] = df_landing['time_sec'].diff()

    # Compute changes
    df_landing['dalt'] = df_landing['gps_alt'].diff()
    df_landing['distance'] = np.sqrt(df_landing['dx']**2 + df_landing['dy']**2)
    df_landing['speed_kmh'] = (df_landing['distance'] / df_landing['dt']) * 3.6

    window = 60  # or whatever you want
    df_landing['cum_distance'] = df_landing['distance'].rolling(window=window).sum()
    df_landing['cum_altitude_change'] = df_landing['dalt'].abs().rolling(window=window).sum()
    df_landing['cum_speed'] = df_landing['speed_kmh'].rolling(window=window).mean()

    # Find landing:
    landing_condition = (
        (df_landing['cum_distance'] < 200) &
        (df_landing['cum_altitude_change'] < 50) &
        (df_landing['cum_speed'] < 10)
    )

    landings = df_landing[landing_condition]
    if not landings.empty:
        landing_time = landings.head(1).time.iloc[0]
        VERBOSE and print(f'[{pilot}] landing:', landing_time)


    # build pandas cols:
    col_time = []
    col_lat = []
    col_lon = []
    col_pressure_alt = []
    col_gps_alt = []
    col_airstart = []
    col_next_tp = []
    col_goal = []
    col_landed = []
    col_distance = []

    turnpoint_counter = 1
    in_goal = False
    is_landed = False

    #for record in tqdm(pilot_igc['fix_records'][1]):
    for record in pilot_igc['fix_records'][1]: # non verbose!
        # {'time': datetime.time(11, 16, 31), 'lat': 46.7004, 'lon': 7.820883333333334, 'validity': 'A', 'pressure_alt': 1181, 'gps_alt': 1275, 'LAD': 1, 'LOD': 3, 'datetime': datetime.datetime(2025, 3, 1, 11, 16, 31, tzinfo=<aerofiles.util.timezone.TimeZoneFix object at 0x762567367e00>)}
        
        # for each record: 
        #  - check if airstart is on
        #  - check if pilot hits first turnpoint => remove turnpoint from path
        #  - if there is no turnpoint left, pilot is in goal / (or ess, depending on modeling)
        #  - compute the progress to goal
        #  - save progress

        task_started = task.airstart <= record['time']
        
        if landing_time is not None:
            is_landed = record['time'] >= landing_time

        x, y, _, _ = utm.from_latlon(record['lat'], record['lon'])
        pilot_position = Point2f(x,y)

        # missuse the first turnpoint as pilot position:
        task.turnpoints[0].center = pilot_position
        task.turnpoints[0].radius = 1 # small radius

        # test for turnpoint 1
        if not in_goal and task_started and task.turnpoints[1].intersect(pilot_position):
            VERBOSE and print(f'[{pilot}] HIT TP{turnpoint_counter} at', record['time'])
            if len(task.turnpoints) >= 3:
                del task.turnpoints[1]
                del path.points[1] # remove coresponding point
                turnpoint_counter += 1            
            else:
                VERBOSE and print(f'[{pilot}] In Goal!')
                in_goal = True
        
        # optimize distance given the updated path and the best config
        if not is_landed:
            optimizer = ShortestPathOptimizer(task, config['lr'], config['itr'], config['crit'], config['weight'], config['back'])
            path = optimizer.shortest_path(path)

        # store values
        col_time.append(record['time'])
        col_lat.append(record['lat'])
        col_lon.append(record['lon'])
        col_pressure_alt.append(record['pressure_alt'])
        col_gps_alt.append(record['gps_alt'])
        col_airstart.append(task_started)
        col_next_tp.append(f'TP{turnpoint_counter+1}')
        col_goal.append(in_goal)
        col_landed.append(is_landed)
        col_distance.append(path.distance())

        #print('Date: ', record['time'], '\tGPS: ', record['gps_alt'], '\tAirstart: ', task.airstart <= record['time'], 'NextTP:', f'TP{turnpoint_counter+1}', 'Goal:', in_goal, '\tDistance: ', path.distance() / 1000.)

    df = pd.DataFrame({
        'time': col_time,
        'lat': col_lat,
        'lon': col_lon,
        'pressure_alt': col_pressure_alt,
        'gps_alt': col_gps_alt,
        'airstart': col_airstart,
        'next_tp': col_next_tp,
        'goal': col_goal,
        'landed': col_landed,
        'distance': col_distance
    })
    #df.to_csv(f'data/dump/{pilot}.csv.gz', index=False, compression="gzip")
    #try:
    #    os.mkdir(f'data/dump/{task_name}/')
    #except OSError:
    #    pass    
    df.to_csv(f'data/dump/{task_name}/{pilot}.csv', index=False)
    VERBOSE and print(f'Processed {pilot}')

    # Visualize:
    #plt.figure(figsize=(10, 6))
    #plt.plot(np.arange(len(df)), df['lon'])
    #plt.plot(np.arange(len(df)), df['lat'])
    #plt.show()




# contains .xctsk and .igc

# Regio Beo
#ROOT_DIRECTORY = 'data/igc/task_2025_03_22' 

# Swiss Leage Cups
#ROOT_DIRECTORY = 'data/igc/swissleague/march/igc6494_2025-03-08'

# TODO: create command line wrapper
#ROOT_DIRECTORY = 'data/igc/swissleague/swiss_regio_grindelwald'
#ROOT_DIRECTORY = 'data/igc/swissleague/swiss_regio_selection'

# Swiss Cup Grindelwald
#ROOT_DIRECTORY = 'data/igc/swissleague/swiss_cup_grindelwald/2025_04_26'
ROOT_DIRECTORY = 'data/igc/swissleague/swiss_cup_grindelwald/2025_04_27'


# scan directory
task_file = None
igc_files = []
for file in os.listdir(ROOT_DIRECTORY):
    if file.lower().endswith('.xctsk'):
        assert task_file is None, 'two task files found!'
        task_name = file.split('.')[0]
        task_file = os.path.join(ROOT_DIRECTORY, file)
    if file.lower().endswith('.igc'):
        igc_files.append(os.path.join(ROOT_DIRECTORY, file))

# Scan igc files for names:
pilots = {}
for igc_file in igc_files:
    with open(igc_file, 'r') as f:
        pilot_igc = igc.Reader().read(f)
        pilot_name = pilot_igc['header'][1]['pilot']
        if pilot_name is not None:
            pilot_name = canonical_name(pilot_igc['header'][1]['pilot'])
        else:
            match = re.search(r"LiveTrack (.+?)\.\d", igc_file)
            pilot_name = canonical_name(match.group(1))
        assert pilot_name not in pilots, 'Dublicated file found! ' + igc_file
        pilots[pilot_name] = igc_file
print("Pilots found:", pilots.keys())


# prepare output
os.makedirs(f'data/dump/{task_name}', exist_ok=True)

original_task = load_from_xctsk(task_file)
#task.turnpoints[-1].radius = 100 # simulate line goal
#airstart = datetime.time(11, 35) # use utc

# Create initial shortest path
center_path = Path.from_center_points(original_task)
optimizer = GridSearchShortestPath(original_task)
#original_path, distances, config = optimizer.run_fast()
original_path, distances, config = optimizer.run_slow()

#pilots = {'benjamin': 'igc/task_2025-03-01-Regio/2025-03-01-XCT-BFA-11.igc',
#           'roger': 'igc/task_2025-03-01-Regio/2025-03-01-XCT-RAE-01.igc',
#           'patrick': 'igc/task_2025-03-01-Regio/2025-03-01-XCT-PMO-01.igc'
#           }

# Select a pilot:
#pilot = 'roger'

# DEBUG:
#for item in pilots.items():
#    if 'benjamin' in item[0]:
#        process_pilot(item)

with concurrent.futures.ProcessPoolExecutor() as executor:
    list(tqdm(executor.map(process_pilot, pilots.items()), total=len(pilots)))


