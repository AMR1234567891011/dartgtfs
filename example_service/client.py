import zmq
import math
from google.transit import gtfs_realtime_pb2

#This notifies a user when a train is about to cross a train crossing in north dallas which is important for my commute.
#Knowing when a train could cross gives me enoguh time to change route in time to not be delayed
#dummy numbers are in right now.
WATCH_LAT = 32
WATCH_LNG = -96
RADIUS_METERS = 500  # 500m


def distance(lat1, lon1, lat2, lon2):
    # haversine
    from math import radians, sin, cos, asin, sqrt
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    R = 6371000  # meters
    return R * c

def main():
    ctx = zmq.Context()
    socket = ctx.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5556")

    socket.setsockopt_string(zmq.SUBSCRIBE, "")

    print("Listening for spot alerts")

    while True:
        data = socket.recv()
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(data)
        for entity in feed.entity:
            if entity.id != "at_grade_crossing":
                continue
            if not hasattr(entity, "lat") or not hasattr(entity, "lng"):
                continue

            lat = entity.lat
            lng = entity.lng

            dist = distance(WATCH_LAT, WATCH_LNG, lat, lng)

            if dist <= RADIUS_METERS:
                print("\n Train crossing soon")
                print(f"Distance: {int(dist)} m")
                print(f"Coords: lat={lat}, lng={lng}")

                if entity.alert.header_text.translation:
                    print("Message:", entity.alert.header_text.translation[0].text)

                print("-------------")

if __name__ == "__main__":
    main()
