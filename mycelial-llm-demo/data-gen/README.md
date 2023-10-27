# data-gen

A very specific helper script for generating queries for a specific database structure.  

Generates a million rows of data to match a database created with 
```sql
CREATE TABLE engine_data(
    ID INT PRIMARY KEY,
    Engine INT,
    Temperature REAL,
    Thrust REAL,
    Timestamp TIMESTAMP
);
```

To use...

```
poetry install 
poetry run generate > mydatafile.sql
```