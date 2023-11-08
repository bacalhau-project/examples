import argparse
from datetime import datetime, timedelta
import json
import os
import random
import time


TOTAL = 1000000

# rowid, engine_id, temperature, thrust, timestamp
TEMPLATE = """
INSERT INTO engine_data VALUES({}, {}, {:.2f}, {:.2f}, '{}');
"""


# CREATE TABLE engine_data(
#     ID INT PRIMARY KEY,
#     Engine INT,
#     Temperature REAL,
#     Thrust REAL,
#     Timestamp TIMESTAMP
# );


def main():
    rowid = 0
    for _x in range(0, TOTAL, 10):
        print("BEGIN TRANSACTION;")
        print("# rowid, engine_id, temperature, thrust, timestamp")
        for _ in range(0, 10):
            rowid = rowid + 1
            q = TEMPLATE.format(
                rowid,
                rand_engine(),  # engine_id
                randf_in_range(0.0, 400.0),  # Temp
                randf_in_range(0.0, 5000.0),  # Thrust
                rand_time(datetime.now() + timedelta(days=5)),
            )

            print(q.strip())
        print("COMMIT;")


def rand_time(until):
    now_unix = time.mktime(datetime.now().timetuple())
    unix = time.mktime(until.timetuple())

    rnd = randf_in_range(now_unix, unix)
    dt = datetime.utcfromtimestamp(rnd)

    # yyyy-MM-dd HH:mm:ss
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def rand_engine():  # 1 - 4
    return random.randint(1, 4)


def randf_in_range(lower, upper):
    return random.uniform(lower, upper)
