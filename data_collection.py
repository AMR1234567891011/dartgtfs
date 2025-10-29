import asyncio
from playwright.async_api import async_playwright
import json, time, signal
import csv
from datetime import datetime
import zmq
import pytz
stop_signal_received = False
agency_tz = pytz.timezone('America/Chicago')
socket,context = None, None
zmq_addr = "tcp://*:5555"
try:
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.bind(zmq_addr)
    print("ZMQ bound to port 5555")
except zmq.ZMQError as e:
    print(f"Failed to bind to port 5555: {e}")
def get_dart_record(json,timestamp):
    return [timestamp, json["id"], json["transitMode"],json["orientation"],json["coordinate"]["lat"],json["coordinate"]["lng"],json["stop"]["id"],json["headSign"],json["route"]["id"],json["trip"]["id"]],json["id"]
def get_dart_record_json(json ,timestamp):
    json['timestamp'] = timestamp
    return json
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://dart.mygopass.org/")
        async def handle_response(resp):
            ts = datetime.now(agency_tz).isoformat()
            try:
                if "vehicles/snapshot" in str(resp.url):
                    ct = resp.headers.get("content-type", "").lower()
                    if "json" in ct:
                        data = await resp.json()
                        content = data.get('content', [])
                        trains = [content for content in content if content["transitMode"] == "LIGHT_RAIL"]
                        trains_l = len(trains)
                        for i in range(0,trains_l):
                            #writer.writerow(get_dart_record(trains[i], ts))
                            socket.send_json(get_dart_record_json(trains[i], ts))
            except Exception as e:
                print("Response handler error:", e)
        page.on("response", handle_response)
        while True:
            await asyncio.sleep(1)
        await browser.close()
asyncio.run(main())
