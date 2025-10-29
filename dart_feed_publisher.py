import zmq
from google.transit import gtfs_realtime_pb2
import datetime
from datetime import timedelta
import pytz

class zmqgtfspublisher:
    def __init__(self, bind_addr="tcp://0.0.0.0:5556"):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(bind_addr)
        print(f"GTFS Alert Publisher bound to {bind_addr}")
    
    def send_alert(self, trip_id, stop_id, delay_minutes, vehicle_id=None):
        agency_tz = pytz.timezone('America/Chicago')
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.timestamp = int(datetime.datetime.now(agency_tz).timestamp())
        entity = feed.entity.add()
        entity.id = f"delay_{trip_id}_{stop_id}"
        informed_entity = entity.alert.informed_entity.add()
        informed_entity.trip.trip_id = str(trip_id) 
        stop_entity = entity.alert.informed_entity.add()
        stop_entity.stop_id = str(stop_id)
        entity.alert.cause = gtfs_realtime_pb2.Alert.OTHER_CAUSE
        entity.alert.effect = gtfs_realtime_pb2.Alert.SIGNIFICANT_DELAYS
        header = entity.alert.header_text.translation.add()
        header.text = f"Delay: {delay_minutes} min"
        description = entity.alert.description_text.translation.add()
        description.text = f"Vehicle experiencing {delay_minutes} minute delay"
        active_period = entity.alert.active_period.add()
        active_period.start = int(datetime.datetime.now(agency_tz).timestamp())
        active_period.end = int((datetime.datetime.now(agency_tz) + timedelta(hours=1)).timestamp())
        alert_bytes = feed.SerializeToString()
        self.socket.send(alert_bytes)
        print(f"Sent GTFS-RT alert: {trip_id} at {stop_id}")