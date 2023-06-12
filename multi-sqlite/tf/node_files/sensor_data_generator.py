# Create sample sensor data for testing
import decimal
import simplejson as json

from datetime import datetime, timedelta
from faker import Faker
from time import sleep, time

import sys

import sqlite3
import tempfile

from apscheduler.schedulers.background import BlockingScheduler

SQLITEDB = "/db/sensor_data.db"
F = Faker()


class Sensor(object):
    def __init__(self, id):
        self.id = id
        self.coord = {"lon": float(round(F.longitude(), 2)), "lat": float(round(F.latitude(), 2))}
        self.temperature = float(decimal.Decimal(F.random.randrange(100, 300)) / 10)
        self.humidity = F.random_int(min=90, max=99)
        self.ph = float(decimal.Decimal(F.random.randrange(70, 100)) / 10)
        self.whc = self.humidity - 30 - F.random_int(min=1, max=10) + float(F.random.randrange(1, 9) / 10)

    # def __iter__(self):
    #     return self

    # def next(self):
    #     message = json.dumps(
    #         {
    #             "id": self.id,
    #             "coord": self.coord,
    #             "date": self.current_dt.strftime("%Y-%m-%d %H:%M"),
    #             "main": {"temperature": self.temperature, "humidity": self.humidity, "ph": self.ph, "whc": self.whc},
    #         }
    #     )


def generateEntry():
    with sqlite3.connect(SQLITEDB) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lat REAL,
            lon REAL,
            date TEXT,
            temperature REAL,
            humidity INTEGER,
            ph REAL,
            whc REAL
        );"""
        )

        # Create a new sensor object
        sensor = Sensor(1)

        conn.execute(
            """INSERT INTO sensor_data (lat, lon, date, temperature, humidity, ph, whc)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sensor.coord["lat"],
                sensor.coord["lon"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                sensor.temperature,
                sensor.humidity,
                sensor.ph,
                sensor.whc,
            ),
        )
        # print("Entered 1")
        # Append-adds at last
        # file1 = open("/node/app_log", "a")  # append mode
        # file1.write("written 1")
        # file1.close()


# Main
if __name__ == "__main__":
    # if arg == "delete", then clear the database and table
    # Read args
    if len(sys.argv) > 1:
        if sys.argv[1] == "delete":
            with sqlite3.connect(SQLITEDB) as conn:
                conn.execute("DROP TABLE IF EXISTS sensor_data")
        elif sys.argv[1] == "print":
            with sqlite3.connect(SQLITEDB) as conn:
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
                rows = cursor.fetchall()
                for row in rows:
                    print(row)
    else:
        scheduler = BlockingScheduler()
        scheduler.add_job(generateEntry, "interval", seconds=1)
        scheduler.start()
