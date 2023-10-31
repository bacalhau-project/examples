import datetime
import random
import pytz
import numpy as np
from collections import OrderedDict
import yaml
import argparse
import time

from faker import Faker

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


def random_bytes():
    return f.random_int(10000, 100000)


resources = [
    "/list",
    "/wp-content",
    "/wp-admin",
    "/explore",
    "/search/tag/list",
    "/app/main/posts",
    "/posts/posts/explore",
    "/apps/cart.jsp?appID=",
]


def generate_session(start_time: datetime) -> list:
    # Based on this - https://github.com/kiritbasu/Fake-Apache-Log-Generator
    sess = []
    ip = f.ipv4()
    user_id = f.user_name()

    sess.append(create_log_entry(ip, user_id, start_time.isoformat(), "GET", "/login", "HTTP/1.1", 200, random_bytes()))
    current_time = start_time

    while True:
        increment = datetime.timedelta(seconds=random.randint(5, 60))
        current_time += increment

        dt = current_time.isoformat()

        uri = random.choice(resources)
        if uri.find("apps") > 0:
            uri += str(random.randint(1000, 10000))

        byt = int(random.gauss(5000, 50))
        sess.append(create_log_entry(ip, user_id, dt, "GET", uri, "HTTP/1.1", 200, byt))

        # Randomly end - on average there should be at least 4 pages
        if random.random() < 0.25:
            break

    increment = datetime.timedelta(seconds=random.randint(10, 120))
    current_time += increment
    dt = current_time.isoformat()

    sess.append(create_log_entry(ip, user_id, dt, "GET", "/logout", "HTTP/1.1", 200, random_bytes()))

    return sess


# For a given timezone, we're going to generate a full day of log entries. The timezone should be passed in as
# an int offset from UTC. For example, if the timezone is UTC-5, then the offset would be -5. We want it to be cyclical
# generating more users during the day and less at night. The number of users will also be passed in
# and we will use that number to identify how to spread them throughout the day
# def generate_day_for_timezone(number_of_users, utc_offset) -> list:


def generate_log_times(days_offset: int, timezone_offset: str, num_users: int) -> list[datetime.datetime]:
    timezone = pytz.FixedOffset(int(timezone_offset) * 60 / 100)

    times = [
        datetime.datetime.combine(
            datetime.date.today() + datetime.timedelta(days=days_offset), datetime.time(hour=hour, minute=minute)
        )
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


# Write a function to take a sess object and output it as a standard Apache log entry
def write_log_entry(sess) -> str:
    return f"{sess['ip']} - {sess['user_id']} [{sess['timestamp']}] {sess['action']} {sess['page']} {sess['http_version']} {sess['http_code']} {sess['bytes']}"


if __name__ == "__main__":
    fake = Faker()

    # Load variables from a yaml file in the current directory called generate_sample_logs.yaml
    # The yaml file should have the following variables:
    # filename: the name of the file to write to
    # days: the number of days to generate logs for
    # users: the number of users to generate logs for
    # timezone: the timezone to generate logs for
    # parser = argparse.ArgumentParser(description="Generate fake log entries and save them to a specified directory.")
    # parser.add_argument(
    #     "-f", "--filename", type=str, nargs="?", help="The filename to save the log file.", default="access.log"
    # )
    # parser.add_argument(
    #     "-d", "--days", type=int, nargs="?", help="The number of days to generate logs for.", default=1
    # )
    # parser.add_argument(
    #     "-u", "--users", type=int, nargs="?", help="The number of users to generate logs for.", default=100
    # )
    # parser.add_argument(
    #     "-t", "--timezone", type=int, nargs="?", help="The timezone to generate logs for.", default=0
    # )
    # args = parser.parse_args()

    # filename = args.filename
    # days = args.days
    # users_per_day = args.users
    # timezone = int(args.timezone) / 100

    with open("generate_sample_logs.yaml") as file:
        data = yaml.safe_load(file)

    filename = data["filename"]
    days = data["days"]
    users_per_day = data["users_per_day"]
    timezone = time.strftime("%z")

    for i in range(days):
        log_times = generate_log_times(i, timezone, users_per_day)
        distribution = OrderedDict()
        for hour in range(24):
            distribution[hour] = 0

        for t in log_times:
            hour = t.hour
            distribution[hour] += 1

        log_lines = []
        for t in log_times:
            for sess in generate_session(t):
                log_lines.append(write_log_entry(sess))

        s = "\n".join(log_lines)

        # Write a loop to append every entry in log_times to a file. Truncate this file if it already exists.
        # The file should be called "access.log" and should be in the current directory
        with open(filename, "a") as filehandle:
            filehandle.write(s)
