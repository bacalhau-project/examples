#!/bin/bash

# Array of URLs to process
urls=(
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-01.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-02.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-03.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-04.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-05.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-06.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-07.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-08.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-09.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-10.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-11.parquet"
    "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2020-12.parquet"
)

# Process each URL
for url in "${urls[@]}"; do
    echo "Processing URL: $url"
    
    # Run the bacalhau job with the URL as template variable
    bacalhau job run download_data_job.yaml --template-vars="url_to_download=$url" --template-vars="filename=$(basename $url)"
    
    # Add a small delay between job submissions
    sleep 1
done