WITH intervals AS (
    SELECT
        DATE_TRUNC('hour', tpep_pickup_datetime) AS pickup_hour,
        FLOOR(EXTRACT(MINUTE FROM tpep_pickup_datetime) / 5) * 5 AS pickup_minute
    FROM
        your_table_name
)
SELECT
    pickup_hour + INTERVAL (pickup_minute) MINUTE AS interval_start,
    AVG(ride_count) AS avg_rides_per_5min
FROM (
    SELECT
        pickup_hour,
        pickup_minute,
        COUNT(*) AS ride_count
    FROM
        intervals
    GROUP BY
        pickup_hour,
        pickup_minute
) AS ride_counts
GROUP BY
    interval_start
ORDER BY
    interval_start;