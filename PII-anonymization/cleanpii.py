import pandas as pd
import hashlib

# Retrive headers from second line
with open('data.csv', 'r') as file:
    file.readline()
    headers = file.readline().strip('#Fields:').split()
# Create a DataFrame
df = pd.read_csv('data.csv', sep='\t', skiprows=[0,1], names=headers)

# Use a lambda function to apply hashing to each row
df['x-edge-location'] = df['x-edge-location'].apply(lambda x: hashlib.sha256(x.encode()).hexdigest())
df['c-ip'] = df['c-ip'].apply(lambda x: hashlib.sha256(x.encode()).hexdigest())
df['x-forwarded-for'] = df['x-forwarded-for'].apply(lambda x: hashlib.sha256(x.encode()).hexdigest())

df.to_csv('anonymized.csv', index=False)