-- Wind Turbine Anomaly Monitoring Queries
-- These queries can be used in Databricks SQL dashboards to monitor data quality

-- =====================================================
-- 1. REAL-TIME ANOMALY RATE
-- =====================================================
-- Shows the current anomaly rate across all turbines
WITH recent_data AS (
  SELECT 
    COUNT(*) as total_records,
    SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as anomaly_count,
    MAX(processing_timestamp) as last_update
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
  WHERE processing_timestamp >= current_timestamp() - INTERVAL 1 HOUR
)
SELECT 
  total_records,
  anomaly_count,
  ROUND(100.0 * anomaly_count / NULLIF(total_records, 0), 2) as anomaly_rate_percent,
  last_update
FROM recent_data;

-- =====================================================
-- 2. ANOMALY TREND BY HOUR
-- =====================================================
-- Shows hourly anomaly trends for the last 24 hours
SELECT 
  DATE_TRUNC('hour', processing_timestamp) as hour,
  COUNT(*) as total_records,
  SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as anomaly_count,
  ROUND(100.0 * SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as anomaly_rate
FROM (
  SELECT processing_timestamp, validation_error 
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
  WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
  
  UNION ALL
  
  SELECT processing_timestamp, NULL as validation_error
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_validated
  WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
)
GROUP BY DATE_TRUNC('hour', processing_timestamp)
ORDER BY hour DESC;

-- =====================================================
-- 3. TOP ANOMALY TYPES
-- =====================================================
-- Identifies the most common types of anomalies
SELECT 
  CASE 
    WHEN validation_error LIKE '%Rotation%wind%' THEN 'Rotation Without Wind'
    WHEN validation_error LIKE '%Vibration%' THEN 'Excessive Vibration'
    WHEN validation_error LIKE '%Power%rotation%' THEN 'Power Without Rotation'
    WHEN validation_error LIKE '%temperature%' THEN 'Temperature Out of Range'
    WHEN validation_error LIKE '%format%' OR validation_error LIKE '%pattern%' THEN 'Format Error'
    ELSE 'Other'
  END as anomaly_type,
  COUNT(*) as occurrence_count,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 2) as percentage
FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
WHERE validation_error IS NOT NULL
  AND processing_timestamp >= current_timestamp() - INTERVAL 7 DAYS
GROUP BY anomaly_type
ORDER BY occurrence_count DESC;

-- =====================================================
-- 4. TURBINE HEALTH SCORES
-- =====================================================
-- Calculates health scores for each turbine based on anomaly rates
WITH turbine_stats AS (
  SELECT 
    turbine_id,
    COUNT(*) as total_readings,
    SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as anomaly_count
  FROM (
    SELECT turbine_id, validation_error 
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
    
    UNION ALL
    
    SELECT turbine_id, NULL as validation_error
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_validated
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
  )
  GROUP BY turbine_id
)
SELECT 
  turbine_id,
  total_readings,
  anomaly_count,
  ROUND(100.0 * (total_readings - anomaly_count) / NULLIF(total_readings, 0), 2) as health_score,
  CASE 
    WHEN anomaly_count = 0 THEN 'Excellent'
    WHEN anomaly_count * 1.0 / total_readings < 0.05 THEN 'Good'
    WHEN anomaly_count * 1.0 / total_readings < 0.15 THEN 'Warning'
    ELSE 'Critical'
  END as health_status
FROM turbine_stats
ORDER BY health_score ASC;

-- =====================================================
-- 5. SITE-LEVEL ANOMALY COMPARISON
-- =====================================================
-- Compares anomaly rates across different sites
SELECT 
  site_id,
  COUNT(*) as total_records,
  SUM(CASE WHEN source = 'anomaly' THEN 1 ELSE 0 END) as anomaly_count,
  ROUND(100.0 * SUM(CASE WHEN source = 'anomaly' THEN 1 ELSE 0 END) / COUNT(*), 2) as anomaly_rate,
  COUNT(DISTINCT turbine_id) as turbine_count
FROM (
  SELECT site_id, turbine_id, 'anomaly' as source
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
  WHERE processing_timestamp >= current_timestamp() - INTERVAL 7 DAYS
  
  UNION ALL
  
  SELECT site_id, turbine_id, 'valid' as source
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_validated
  WHERE processing_timestamp >= current_timestamp() - INTERVAL 7 DAYS
)
GROUP BY site_id
ORDER BY anomaly_rate DESC;

-- =====================================================
-- 6. CRITICAL VIBRATION ALERTS
-- =====================================================
-- Identifies turbines with critical vibration levels
SELECT 
  turbine_id,
  site_id,
  MAX(vibration_x) as max_vibration_x,
  MAX(vibration_y) as max_vibration_y,
  MAX(vibration_z) as max_vibration_z,
  MAX(GREATEST(vibration_x, vibration_y, vibration_z)) as max_vibration_overall,
  COUNT(*) as critical_reading_count,
  MAX(processing_timestamp) as last_critical_reading
FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
WHERE (vibration_x > 50 OR vibration_y > 50 OR vibration_z > 50)
  AND processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
GROUP BY turbine_id, site_id
ORDER BY max_vibration_overall DESC;

-- =====================================================
-- 7. DATA QUALITY METRICS SUMMARY
-- =====================================================
-- Overall data quality dashboard metrics
WITH quality_metrics AS (
  SELECT 
    'Last Hour' as time_period,
    COUNT(*) as total_records,
    SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as invalid_records,
    COUNT(DISTINCT turbine_id) as active_turbines,
    COUNT(DISTINCT site_id) as active_sites
  FROM (
    SELECT turbine_id, site_id, validation_error
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 1 HOUR
    
    UNION ALL
    
    SELECT turbine_id, site_id, NULL as validation_error
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_validated
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 1 HOUR
  )
  
  UNION ALL
  
  SELECT 
    'Last 24 Hours' as time_period,
    COUNT(*) as total_records,
    SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as invalid_records,
    COUNT(DISTINCT turbine_id) as active_turbines,
    COUNT(DISTINCT site_id) as active_sites
  FROM (
    SELECT turbine_id, site_id, validation_error
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
    
    UNION ALL
    
    SELECT turbine_id, site_id, NULL as validation_error
    FROM expanso_databricks_workspace.sensor_readings.sensor_readings_validated
    WHERE processing_timestamp >= current_timestamp() - INTERVAL 24 HOURS
  )
)
SELECT 
  time_period,
  total_records,
  invalid_records,
  total_records - invalid_records as valid_records,
  ROUND(100.0 * (total_records - invalid_records) / NULLIF(total_records, 0), 2) as data_quality_score,
  active_turbines,
  active_sites
FROM quality_metrics
ORDER BY 
  CASE time_period 
    WHEN 'Last Hour' THEN 1 
    WHEN 'Last 24 Hours' THEN 2 
  END;

-- =====================================================
-- 8. ANOMALY DETECTION EFFECTIVENESS
-- =====================================================
-- Tracks how many anomalies are caught by validation
SELECT 
  DATE(processing_timestamp) as date,
  COUNT(*) as anomalies_detected,
  COUNT(DISTINCT turbine_id) as affected_turbines,
  COUNT(DISTINCT 
    CASE 
      WHEN validation_error LIKE '%Rotation%wind%' THEN 'rotation_without_wind'
      WHEN validation_error LIKE '%Vibration%' THEN 'excessive_vibration'
      WHEN validation_error LIKE '%Power%rotation%' THEN 'power_without_rotation'
      WHEN validation_error LIKE '%temperature%' THEN 'temperature_range'
      ELSE 'other'
    END
  ) as unique_anomaly_types,
  ROUND(AVG(
    CASE 
      WHEN validation_error LIKE '%Vibration%' THEN 
        GREATEST(vibration_x, vibration_y, vibration_z)
      ELSE NULL
    END
  ), 2) as avg_vibration_when_anomalous
FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
WHERE validation_error IS NOT NULL
  AND processing_timestamp >= current_timestamp() - INTERVAL 30 DAYS
GROUP BY DATE(processing_timestamp)
ORDER BY date DESC;

-- =====================================================
-- 9. CORRELATION ANALYSIS
-- =====================================================
-- Identifies correlations between anomalies and conditions
SELECT 
  CASE 
    WHEN wind_speed < 3 THEN 'Low Wind (<3 m/s)'
    WHEN wind_speed < 10 THEN 'Moderate Wind (3-10 m/s)'
    WHEN wind_speed < 20 THEN 'Good Wind (10-20 m/s)'
    ELSE 'High Wind (>20 m/s)'
  END as wind_condition,
  COUNT(*) as total_readings,
  SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) as anomaly_count,
  ROUND(100.0 * SUM(CASE WHEN validation_error IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 2) as anomaly_rate,
  AVG(power_output) as avg_power_output,
  AVG(rotation_speed) as avg_rotation_speed
FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
WHERE processing_timestamp >= current_timestamp() - INTERVAL 7 DAYS
GROUP BY wind_condition
ORDER BY 
  CASE wind_condition
    WHEN 'Low Wind (<3 m/s)' THEN 1
    WHEN 'Moderate Wind (3-10 m/s)' THEN 2
    WHEN 'Good Wind (10-20 m/s)' THEN 3
    ELSE 4
  END;

-- =====================================================
-- 10. ALERT PRIORITY QUEUE
-- =====================================================
-- Prioritizes turbines needing immediate attention
WITH recent_anomalies AS (
  SELECT 
    turbine_id,
    site_id,
    COUNT(*) as anomaly_count,
    MAX(processing_timestamp) as last_anomaly,
    COLLECT_SET(
      CASE 
        WHEN validation_error LIKE '%Vibration%' THEN 'vibration'
        WHEN validation_error LIKE '%Rotation%wind%' THEN 'rotation'
        WHEN validation_error LIKE '%Power%' THEN 'power'
        WHEN validation_error LIKE '%temperature%' THEN 'temperature'
        ELSE 'other'
      END
    ) as anomaly_types,
    MAX(GREATEST(vibration_x, vibration_y, vibration_z)) as max_vibration
  FROM expanso_databricks_workspace.sensor_readings.sensor_readings_anomalies
  WHERE validation_error IS NOT NULL
    AND processing_timestamp >= current_timestamp() - INTERVAL 4 HOURS
  GROUP BY turbine_id, site_id
)
SELECT 
  turbine_id,
  site_id,
  anomaly_count,
  last_anomaly,
  array_join(anomaly_types, ', ') as anomaly_types,
  max_vibration,
  CASE 
    WHEN max_vibration > 60 THEN 1  -- Critical vibration
    WHEN array_contains(anomaly_types, 'vibration') THEN 2  -- Any vibration issue
    WHEN anomaly_count > 10 THEN 3  -- Frequent anomalies
    WHEN array_contains(anomaly_types, 'power') THEN 4  -- Power issues
    ELSE 5  -- Other
  END as priority_score,
  CASE 
    WHEN max_vibration > 60 THEN 'CRITICAL - Immediate inspection required'
    WHEN array_contains(anomaly_types, 'vibration') THEN 'HIGH - Vibration anomaly detected'
    WHEN anomaly_count > 10 THEN 'MEDIUM - Frequent anomalies'
    WHEN array_contains(anomaly_types, 'power') THEN 'MEDIUM - Power generation issue'
    ELSE 'LOW - Monitor'
  END as action_required
FROM recent_anomalies
ORDER BY priority_score, anomaly_count DESC
LIMIT 20;