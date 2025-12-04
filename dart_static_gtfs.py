
import pandas as pd
import math
from datetime import datetime, timedelta
import zmq
import pytz
from dart_feed_publisher import zmqgtfspublisher
class gtfs_schedule:
    stops = {} # (stop_id, lat, lng)
    train_routes = {} # (route_id, name)
    train_trips = {} # (trip_id, )
    schedule = {}
    train_stop_times = {}
    vehicles = {}
    gtfs_static_path = None
    context = None
    socket = None
    zmq_addr = None
    gtfs_publisher = None
    
    def __init__(self, gtfs_static_path= "./google_transit_new", zmq_addr="tcp://127.0.0.1:5555", zmq_pub_addr="tcp://0.0.0.0:5556", spot=None):
        self.gtfs_publisher = zmqgtfspublisher(zmq_pub_addr)
        self.gtfs_static_path = gtfs_static_path
        self.zmq_addr = zmq_addr
        routes_df = pd.read_csv(f"{self.gtfs_static_path}/routes.txt")
        self.train_routes = routes_df.loc[routes_df['route_id'] >= 26777].set_index("route_id").to_dict("index")
        self.stops = pd.read_csv(f"{self.gtfs_static_path}/stops.txt").set_index("stop_id").to_dict("index")
        trips_df = pd.read_csv(f"{self.gtfs_static_path}/trips.txt")
        self.train_trips = trips_df.loc[trips_df["route_id"] >= 26777].set_index("trip_id").to_dict("index")
        stop_times_df = pd.read_csv(f"{self.gtfs_static_path}/stop_times.txt")
        stop_times_df = stop_times_df.loc[stop_times_df["trip_id"] >= 26777]
        service_times_df = pd.read_csv(f"{self.gtfs_static_path}/calendar.txt")
        self.schedule = service_times_df.set_index("service_id").to_dict("index")
        for route in routes_df.loc[routes_df['route_id'] >= 26777, 'route_id'].unique():
            visited_stops = {}
            for trip in trips_df.loc[trips_df['route_id'] == route, 'trip_id'].unique():
                for stop in stop_times_df.loc[stop_times_df['trip_id'] == trip, 'stop_id'].unique():
                    if stop not in visited_stops:
                        visited_stops[stop] = True
        self.service_times = trips_df.loc[trips_df["route_id"] >= 26777].drop_duplicates(subset="service_id").set_index("service_id").to_dict("index")
        # Build mapping: trip_id -> list of stops in order
        for trip_id, group in stop_times_df.groupby("trip_id"):
            # Ensure ordering by stop_sequence
            if trip_id not in self.train_trips: #not a train trip
                continue
            if self.train_trips[trip_id]['service_id'] == 13: #filter out a special calendar day like texas state fair
                continue
            if trip_id in self.train_trips:
                stops_list = group.sort_values("stop_sequence")[["stop_id", "arrival_time", "departure_time"]].to_dict("records")
                self.train_stop_times[trip_id] = stops_list
                self.train_stop_times[trip_id] = gtfs_to_dated(stops_list, datetime.today().strftime('%Y%m%d'))
        if self.zmq_setup():
            if not spot:
                self.zmq_poll()
            else:
                self.spot = spot
                self.spot_poll()
    def zmq_setup(self):
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.PULL)
            self.socket.connect(self.zmq_addr)
            print("ZMQ connect to port 5555")
            return True
        except zmq.ZMQError as e:
            print(f"Failed to connect to port 5555: {e}")
            return False
    def spot_poll(self):#poll a lng, lat pair and see if trains are within some distance
        spot_lat,spot_lng,rad = self.spot
        while True:
            response = self.socket.recv_json()
            ts, trip_id, stop_id, lat, lng, vehicle_id = response['timestamp'], int(response['trip']['id']), int(response['stop']['id']), response['coordinate']['lat'], response['coordinate']['lng'], response['id']
            if trip_id not in self.train_stop_times:
                continue
            if stop_id not in self.stops:
                continue
            if vehicle_id not in self.vehicles:
                self.vehicles[vehicle_id] = {'trip_id': trip_id, 'stops': set()}
            dist = distance(spot_lat, spot_lng, lat, lng)
            if dist <= rad:
                self.gtfs_publisher.send_spot_alert(dist // 30 + 3, lat, lng)
    def zmq_poll(self):
        while True:
            response = self.socket.recv_json()
            ts, trip_id, stop_id, lat, lng, vehicle_id = response['timestamp'], int(response['trip']['id']), int(response['stop']['id']), response['coordinate']['lat'], response['coordinate']['lng'], response['id']
            if trip_id not in self.train_stop_times:
                continue
            if stop_id not in self.stops:
                continue
            if vehicle_id not in self.vehicles:
                self.vehicles[vehicle_id] = {'trip_id': trip_id, 'stops': set()}
            vehicle = self.vehicles[vehicle_id]
            if stop_id not in vehicle['stops']:
                #check if close to next stop and check if on time
                if self.is_close(trip_id, stop_id, lat, lng) < 100:
                    vehicle['stops'].add(stop_id)
                    est_ts = self.get_est_time(trip_id, stop_id)
                    if est_ts < ts:
                        print(f'LATE   close? {int(self.is_close(trip_id, stop_id, lat, lng))} trip_id {trip_id} stop_id {stop_id} id: {vehicle_id}')
                        delay  = get_minute_diff(est_ts, ts)
                        self.gtfs_publisher.send_alert(trip_id, stop_id, delay, vehicle_id)
                        #late alert
                    else:
                        print(f'ONTIME close? {int(self.is_close(trip_id, stop_id, lat, lng))} trip_id {trip_id} stop_id {stop_id} id: {vehicle_id}')
                        #on time alert
    def get_est_time(self, trip_id, stop_id):
        if trip_id not in self.train_stop_times or stop_id not in self.stops:
            return None
        stops_list = self.train_stop_times[trip_id]
        for stop in stops_list:
            if stop['stop_id'] == stop_id:
                return stop['arrival_time']
    def is_close(self, trip_id, stop_id, lat, lng):
        if trip_id not in self.train_stop_times or stop_id not in self.stops:
            return None
        stops_list = self.train_stop_times[trip_id]
        for stop in stops_list:
            if stop['stop_id'] == stop_id:
                stop_info = self.stops[stop_id]
                return distance(stop_info['stop_lat'], stop_info['stop_lon'], lat, lng)


#Given a time or not, convert a trip_id time relative schedule into a real one
def gtfs_to_dated(trip_stop_times, service_date, reference_day_of_week=None):
    base_date = datetime.strptime(service_date, "%Y%m%d").date() # get current day
    if reference_day_of_week is not None: # get refrence day
        days_diff = (reference_day_of_week - base_date.weekday()) % 7
        base_date = base_date + timedelta(days=days_diff)
    agency_tz = pytz.timezone('America/Chicago')
    def parse_gtfs_time(gtfs_time):
        hours, minutes, seconds = map(int, gtfs_time.split(':'))
        days = hours // 24
        hours = hours % 24
        return agency_tz.localize(datetime.combine(base_date, datetime.min.time()) + timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds))
    result = []
    for stop in trip_stop_times:
        arrival_dt = parse_gtfs_time(stop['arrival_time'])
        departure_dt = parse_gtfs_time(stop['departure_time'])
        result.append({
            'stop_id': stop['stop_id'],
            'arrival_time': arrival_dt.isoformat(),
            'departure_time': departure_dt.isoformat()
        })
    return result
def get_minute_diff(ts1_str: str, ts2_str: str) -> int:
    agency_tz = pytz.timezone('America/Chicago')
    def parse_ts(ts_str):
        if ts_str.endswith('Z'):
            return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return datetime.fromisoformat(ts_str)
    ts1 = parse_ts(ts1_str).astimezone(agency_tz.utc)
    ts2 = parse_ts(ts2_str).astimezone(agency_tz.utc)
    diff = ts1 - ts2
    return int(abs(diff.total_seconds()) / 60)
def distance(lat1, lon1, lat2, lon2): #haversine
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    R = 6371000
    return R * c
## Runnning the stuff down here
# WATCH_LAT = 32
# WATCH_LNG = -96
# RADIUS_METERS = 500
# schedule = gtfs_schedule(spot=(WATCH_LAT, WATCH_LNG, RADIUS_METERS))
schedule = gtfs_schedule()
