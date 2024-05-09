import pymongo
import json
from datetime import datetime
import os

# Connect to MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["cpu_memory_records"]
collection = db["records"]

# Function to parse query tring and retrieve records
def query_records(query_str):
    query_dict = json.loads(query_str)

    print(query_dict)

    records = collection.find(query_dict)
    return list(records)

def formatResults(results):
    formattedResults = json.dumps({'results': results})
    return formattedResults


query_str = os.environ.get("QUERY")

if query_str == "" or query_str is None:
    output = formatResults([])
    print(output)
    os._exit(1)

result = query_records(query_str)

# Print the queried records
print("Records with query:", query_str)
for record in result:
    print(record)
