
from datetime import datetime
import utm
from aerofiles import igc
import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle

'''
This Script is used to analyze speed record attempts.
'''

def euclidean_dist(ax, ay, bx, by):
    return math.sqrt((ax-bx)**2 + (ay-by)**2)

class Point:

    def __init__(self, x, y, time=None):        
        self.x = x
        self.y = y   
        self.time = time

    def plot(self, label):
        plt.plot(self.x, self.y, 'kx')  # black x
        plt.text(self.x + 1, self.y + 1, label, fontsize=12, color='black')

    def distance(self, other):
        return euclidean_dist(self.x, self.y, other.x, other.y) 
    
class Turnpoint:

    def __init__(self, lat, lon, radius):
        # TODO: check conversion
        x, y, _, _ = utm.from_latlon(lat, lon)
        self.center = Point(x, y)
        self.radius = 400        
    
    def distance(self, other):
        return self.center.distance(other.center)

    def hit(self, point):        
        return self.center.distance(point) <= self.radius
    
class IGCFile:

    def __init__(self, filename):
        self.filename = filename
        
    def read_points(self):
        points = []
        with open(self.filename, 'r') as f:
            pilot_igc = igc.Reader().read(f)
        
        for record in pilot_igc['fix_records'][1]:
            time = record['time']
            ## TODO: check for zone 32T
            x, y, _, _ = utm.from_latlon(record['lat'], record['lon'])            
            
            point = Point(x, y, time) # point in utm
            points.append(point)
        return points

class Course:

    def __init__(self, start, tps, end):
        self.start = start
        self.tps = tps
        self.end = end
    
    def assert_closed(self):
        closed = self.start.center.x == self.end.center.x \
            and self.start.center.y == self.end.center.y \
            and self.start.radius == self.end.radius
        assert closed, 'The course is not closed!'


class Track:

    def __init__(self, igc_file, course, distance_total_fai):
        self.igc_file = igc_file
        self.course = course
        self.distance_total_fai = distance_total_fai

        # distances
        self.distance_short = 0
        self.distance_total = 0

        # points of interest
        self.start_a = None
        self.start_b = None
        self.end_a = None
        self.end_b = None
        self.difference_seconds = 0

        # prepare:
        self.points = self.igc_file.read_points()
        self.course.assert_closed()
        
        # process:        
        self.validate_turnpoints()
        self.compute_distance()
        self.compute_times()
        self.compute_performance()    

    
    # Check if every turnpoint has been hit. Will be double checked for timeings
    def validate_turnpoints(self):
        turnpoints = [self.course.start, *self.course.tps, self.course.end]
        turnpoint_idx = 0
        for point in self.points:
            if turnpoints[turnpoint_idx].hit(point):
                print("HIT Turnpoint Nr", turnpoint_idx+1)
                turnpoint_idx += 1
                if len(turnpoints) == turnpoint_idx:
                    break
        assert turnpoint_idx == len(turnpoints), 'Not all Turnpoints validated!'
        print('All Turnpoints hit!')
    
    # Computes the distance, but as FAI uses a little different approach this does not matter
    def compute_distance(self):
        # TODO: move to course ?
        a = self.course.start
        b = self.course.tps[0]
        distance = a.distance(b)   
        self.distance_short = distance - 800
        self.distance_total = self.distance_short*2
        print('Distance between turnpoint center:', distance, 'Shortest Fly Distance:', self.distance_short, 'Total Distance:', self.distance_total, 'Total Distance FAI:', self.distance_total_fai)
    
    # Compute the points of interest and the pessimistic time between.
    def compute_times(self):
        
        # Relevant points for time:
        # start a is last point inside start cylinder
        # start b is first point after the start cylinder
        # end a is last point outside the end cylinder
        # end b is the first point inside the end cylinder

        # pessimistic timeing: time(end b) - time(start a).
        # TODO: interpolate!

        # Checks if every turnpoint is hit inbetween.

        tps_counter = 0
        turnpoint = self.course.start
        inside = False
        for i,point in enumerate(self.points):
            if not inside and turnpoint.hit(point):
                inside = True
                
                if turnpoint == self.course.tps[tps_counter]:
                    # hit tpXX:
                    print('hit TP', tps_counter+1)
                    inside = False                    
                    if len(self.course.tps)-1 == tps_counter:
                        turnpoint = self.course.end # goto end                        
                    else:
                        tps_counter += 1
                        turnpoint = self.course.tps[tps_counter]
                    continue

                if turnpoint == self.course.end:
                    # hit end cylinder
                    print('hit end')
                    self.end_a = self.points[i-1]
                    self.end_b = self.points[i]
                    self.end_track = self.points[i-10:i+10]
                    break                 

            if inside and not turnpoint.hit(point):
                if turnpoint == self.course.start:
                    print('left the start')
                    # left the start cylinder:
                    self.start_a = self.points[i-1]
                    self.start_b = self.points[i]
                    self.start_track = self.points[i-10:i+10]
                    inside = False
                    turnpoint = self.course.tps[0] # goto first turnpoint
            
        print('Pessimistic timing:')
        start_time = datetime.strptime(str(self.start_a.time), "%H:%M:%S")
        end_time = datetime.strptime(str(self.end_b.time), "%H:%M:%S")
        self.difference_seconds = (end_time - start_time).total_seconds()
        print('start:', self.start_a.time, 'end:', self.end_b.time, 'difference:', self.difference_seconds/3600, 'h')

    def compute_performance(self):
        print('~~~ PERFORMANCE ~~~')
        print(self.distance_total_fai / (self.difference_seconds/3600) / 1000., 'km/h')
        print('~~~ Optimistic (-2s)')
        print(self.distance_total_fai / ((self.difference_seconds-2)/3600) / 1000., 'km/h')

    def plot(self):
        
        # Define the center point and radius
        center = (self.course.start.center.x, self.course.start.center.y)
        radius = self.course.start.radius

        # Create a plot
        fig, ax = plt.subplots()

        # Add a circle
        circle = Circle(center, radius, fill=True, color='darkred', alpha=0.4, linewidth=2)
        ax.add_patch(circle)        
        ax.plot(center[0], center[1], 'ro')  # red dot at center

        # Track lines:
        xs = [p.x for p in self.start_track]
        ys = [p.y for p in self.start_track]
        ax.plot(xs, ys, color='orange')
        
        xs = [p.x for p in self.end_track]
        ys = [p.y for p in self.end_track]
        ax.plot(xs, ys, color='orange')

        # plot the points:
        self.start_a.plot(f"start a: {self.start_a.time}")
        self.start_b.plot(f"start b: {self.start_b.time}")
        self.end_a.plot(f"end a: {self.end_a.time}")
        self.end_b.plot(f"end b: {self.end_b.time}")

        ax.set_aspect('equal')

        plt.grid(True)
        plt.show()

            

                




if __name__ == '__main__':

    # IGC File:
    igc_file = IGCFile('/home/benjamin/Nextcloud/Paraglide/Records/Flightplans/Speed/100km-out-return/attempt_2025-04-04/2025-04-04-XCT-BFA-07_xcontest.igc')

    # Create Track:
    start = Turnpoint(46.325863, 8.005584, 400)
    tp1 = Turnpoint(46.278496, 7.342815, 400)
    end = Turnpoint(46.325863, 8.005584, 400)
    course = Course(start, [tp1], end)    

    # by FAI Distance Calculator
    distance_fai = 2 * (51.33066768208024-0.800)*1000

    track = Track(igc_file, course, distance_fai)
    track.plot()


