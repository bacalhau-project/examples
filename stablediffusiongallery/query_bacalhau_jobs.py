import json
import os

command = "bacalhau list -n 10 --all --output json"

out = os.popen(command).read()

jobs = json.loads(out)
for job in jobs:
    print(job["ID"])
