import pandas as pd
import hashlib

# Create a DataFrame
df = pd.read_csv('data.csv')

# Use a lambda function to apply hashing to each row
df['LCLid'] = df['LCLid'].apply(lambda x: hashlib.sha256(x.encode()).hexdigest())

df.to_csv('anonymized.csv', index=False)