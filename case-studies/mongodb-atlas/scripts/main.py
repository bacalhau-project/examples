import pymongo
import random
import time
import psutil
import time

p = psutil.Process()

client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["cpu_memory_records"]
collection = db["records"]

def get_cpu_usage():

	cpu_usage = {}

	num_cores = psutil.cpu_count()

	for process in psutil.process_iter(['pid', 'name', 'cpu_percent']):
		try:

			pid = process.info['pid']
			name = process.info['name']
			cpu_percent = process.info['cpu_percent']

			if cpu_percent is not None:

				normalized_cpu_percent = cpu_percent / num_cores
				cpu_usage[pid] = (name, normalized_cpu_percent)

		except (psutil.NoSuchProcess, psutil.AccessDenied):
			pass

	return cpu_usage

def find_max_cpu_usage(cpu_usage):

	max_pid = None
	max_usage = -1

	for pid, (_, usage) in cpu_usage.items():
		if usage is not None and usage > max_usage:
			max_pid = pid
			max_usage = usage

	return max_pid, max_usage

def generate_record(system_cpu_used, highest_use_process, process_cpu_used, system_mem_usd):

	timestamp = time.time()

	record = {
		"timestamp": timestamp,
		"system_cpu_used": system_cpu_used,
		"system_mem_used": system_mem_usd,
		"highest_use_process" : highest_use_process,
		"process_cpu_used" : process_cpu_used
	}

	return record

while True:

	SYSTEM_CPU_USED = get_cpu_usage()
	cpu_utilisation_percentage = psutil.cpu_percent(percpu=False)

	if SYSTEM_CPU_USED:
		max_pid, max_usage = find_max_cpu_usage(SYSTEM_CPU_USED)

		if max_pid is not None:
			process_name = SYSTEM_CPU_USED[max_pid][0]

			cpu_percentage = psutil.cpu_percent(percpu=False)
			memory_percent = psutil.virtual_memory().percent

			record = generate_record(cpu_utilisation_percentage, process_name, max_usage, memory_percent)

			print(record)

			collection.insert_one(record)

	time.sleep(1 / 3)
