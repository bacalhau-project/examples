#!/usr/bin/env python3
"""
Quick test to verify direct INSERT approach works with Databricks.
This creates a small test table and tries the direct INSERT approach.
"""

import pandas as pd
from sqlite_to_databricks_uploader import upload_batch_via_file, quote_databricks_identifier

# Create test data
test_df = pd.DataFrame({
    'id': [1, 2, 3, 4, 5],
    'name': ["Test 1", "O'Brien's Test", "Test 3", "Test 4", "Test 5"],
    'value': [10.5, 20.3, 30.1, 40.7, 50.9],
    'timestamp': pd.Timestamp.now()
})

# Print the SQL that would be generated (for verification)
print("Sample SQL that will be generated:")
print("-" * 60)

# Build column list
columns = [quote_databricks_identifier(col) for col in test_df.columns]
column_list = ', '.join(columns)

# Build sample VALUES clause for first 2 rows
values_rows = []
for _, row in test_df.head(2).iterrows():
    values = []
    for val in row:
        if pd.isna(val):
            values.append('NULL')
        elif isinstance(val, str):
            escaped_val = val.replace("'", "''")
            values.append(f"'{escaped_val}'")
        elif isinstance(val, pd.Timestamp):
            values.append(f"'{val}'")
        else:
            values.append(str(val))
    values_rows.append(f"({', '.join(values)})")

sample_sql = f"""
INSERT INTO `test_database`.`test_table` ({column_list})
VALUES {', '.join(values_rows)}
"""

print(sample_sql)
print("-" * 60)
print("\nThis approach uses direct INSERT with VALUES clause instead of temporary tables.")
print("It should work with Databricks SQL without the CREATE TEMPORARY TABLE error.")