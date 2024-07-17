import pandas as pd
import json
import re
from faker import Faker

# Read the file contents
with open('data.json', 'r') as file:
    data = file.readlines()  # Read as lines

# Process each line as a separate JSON object
processed_data = []
for line in data:
    # Replace single quotes with double quotes
    line = line.replace("'", '"')

    # Fix datetime.date objects
    line = re.sub(r'datetime\.date\((\d+), (\d+), (\d+)\)', r'"\1-\2-\3"', line)

    # Load the JSON string into a dictionary
    try:
        processed_data.append(json.loads(line))
    except json.JSONDecodeError as e:
        line.strip()

# Create a DataFrame
df = pd.DataFrame(processed_data)

fake = Faker()

# Use a lambda function to apply the Faker methods to each row
df['address'] = df.apply(lambda row: fake.address(), axis=1)
df['mail'] = df.apply(lambda row: fake.email(), axis=1)
df['name'] = df.apply(lambda row: fake.name(), axis=1)

df.to_csv('anonymized.csv', index=False)