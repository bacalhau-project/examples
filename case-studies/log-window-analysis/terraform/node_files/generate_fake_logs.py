import datetime
from faker import Faker
import random
import pytz
import numpy as np
from collections import OrderedDict

f = Faker()

# "238.165.17.148 - Selena [10/Oct/2000:13:57:21] GET /amelia.mp3 HTTP/1.0 200 767520"


# Build an object that represents a user session. It should have the following properties
def create_log_entry(ip, user_id, timestamp, action, page, http_version, http_code, bytes) -> object:
    return {
        "ip": ip,
        "user_id": user_id,
        "timestamp": timestamp,
        "action": action,
        "page": page,
        "http_version": http_version,
        "http_code": http_code,
        "bytes": bytes,
    }


#    return f"{ip} - {user_id} [{timestamp}] {action} {page} {http_version} {http_code} {bytes}"


def random_bytes():
    return f.unique.random_int(10000, 100000)


def generate_session(start_time: datetime) -> list:
    sess = []
    ip = f.ipv4()
    user_id = f.user_name()

    sess.append(create_log_entry(ip, user_id, start_time, "GET", "/login", "HTTP/1.1", 200, random_bytes))
    current_time = start_time

    while True:
        increment = datetime.timedelta(seconds=random.randint(10, 120))
        current_time += increment

        dt = current_time.strftime("%d/%b/%Y:%H:%M:%S")

        byt = int(random.gauss(5000, 50))
        sess.append(create_log_entry(ip, user_id, dt, "GET", f.uri(), "HTTP/1.1", 200, byt))

        # Randomly end - on average there should be at least 4 pages
        if random.random() < 0.25:
            break

    increment = datetime.timedelta(seconds=random.randint(10, 120))
    current_time += increment

    sess.append(create_log_entry(ip, user_id, current_time, "GET", "/logout", "HTTP/1.1", 200, random_bytes()))

    return sess


# For a given timezone, we're going to generate a full day of log entries. The timezone should be passed in as
# an int offset from UTC. For example, if the timezone is UTC-5, then the offset would be -5. We want it to be cyclical
# generating more users during the day and less at night. The number of users will also be passed in
# and we will use that number to identify how to spread them throughout the day
# def generate_day_for_timezone(number_of_users, utc_offset) -> list:


def generate_log_entries(timezone_offset: int, num_users: int) -> list[datetime.datetime]:
    timezone = pytz.FixedOffset(timezone_offset * 60)

    times = [
        datetime.datetime.combine(datetime.date.today(), datetime.time(hour=hour, minute=minute))
        for hour in range(24)
        for minute in range(60)
    ]

    times = [time.replace(tzinfo=pytz.UTC).astimezone(timezone) for time in times]

    cycle = 0.95 * np.sin(2 * np.pi * (np.array(range(1440)) / 1440)) + 0.05
    cycle = (cycle + 1) / 2

    # convert cycle values to probabilities
    probabilities = cycle / np.sum(cycle)

    user_times = []
    for _ in range(num_users):
        # choose a random minute based on the probabilities
        minute = np.random.choice(range(1440), p=probabilities)
        # Add seconds and microseconds to the timestamp to make it unique
        unique_time = times[minute] + datetime.timedelta(
            seconds=random.randint(0, 59), microseconds=random.randint(0, 999999)
        )
        user_times.append(unique_time)

    return user_times


if __name__ == "__main__":
    # print(generate_session(datetime.datetime.now()))
    # Usage:
    log_times = generate_log_entries(-5, 2000)
    distribution = OrderedDict()
    for hour in range(24):
        distribution[hour] = 0

    for time in log_times:
        hour = time.hour
        distribution[hour] += 1
    print(distribution)
