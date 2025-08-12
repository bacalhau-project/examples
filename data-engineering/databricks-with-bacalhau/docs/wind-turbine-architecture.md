# Wind Turbine Data Pipeline Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              WIND FARM DEPLOYMENTS                                  │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  US-EAST-1 Region                          US-WEST-2 Region                        │
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │   Wind Farm A   │                       │   Wind Farm C   │                    │
│  │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                       │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                    │
│  │  150 Turbines   │                       │  200 Turbines   │                    │
│  │ [Expanso Nodes] │                       │ [Expanso Nodes] │                    │
│  └────────┬────────┘                       └────────┬────────┘                    │
│           │                                          │                             │
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │   Wind Farm B   │                       │   Wind Farm D   │                    │
│  │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                       │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                    │
│  │  175 Turbines   │                       │  125 Turbines   │                    │
│  │ [Expanso Nodes] │                       │ [Expanso Nodes] │                    │
│  └────────┬────────┘                       └────────┬────────┘                    │
│           │                                          │                             │
│           ▼                                          ▼                             │
│     SQLite → S3                               SQLite → S3                          │
│                                                                                     │
│  EU-WEST-1 Region                          AP-SOUTHEAST-1 Region                   │
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │   Wind Farm E   │                       │   Wind Farm G   │                    │
│  │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                       │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                    │
│  │  225 Turbines   │                       │  100 Turbines   │                    │
│  │ [Expanso Nodes] │                       │ [Expanso Nodes] │                    │
│  └────────┬────────┘                       └────────┬────────┘                    │
│           │                                          │                             │
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │   Wind Farm F   │                       │   Wind Farm H   │                    │
│  │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                       │  🌬️ 🌬️ 🌬️ 🌬️ 🌬️  │                    │
│  │  300 Turbines   │                       │  150 Turbines   │                    │
│  │ [Expanso Nodes] │                       │ [Expanso Nodes] │                    │
│  └────────┬────────┘                       └────────┬────────┘                    │
│           │                                          │                             │
│           ▼                                          ▼                             │
│     SQLite → S3                               SQLite → S3                          │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           S3 DATA LAKE ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  Pipeline Stage Buckets (us-west-2)                                                │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-       │          │ 📦 expanso-databricks-       │         │
│  │    ingestion                │          │    validated               │         │
│  │    └── ingestion/           │          │    └── validated/         │         │
│  │        └── year=2024/       │          │        └── year=2024/     │         │
│  │            └── month=01/    │          │            └── month=01/  │         │
│  └─────────────────────────────┘          └─────────────────────────────┘         │
│                                                                                     │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-       │          │ 📦 expanso-databricks-       │         │
│  │    enriched                 │          │    aggregated              │         │
│  │    └── enriched/            │          │    └── aggregated/        │         │
│  │        └── year=2024/       │          │        └── year=2024/     │         │
│  └─────────────────────────────┘          └─────────────────────────────┘         │
│                                                                                     │
│  Support Buckets                                                                   │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-       │          │ 📦 expanso-databricks-       │         │
│  │    checkpoints              │          │    metadata                │         │
│  │    └── checkpoints/         │          │    └── metadata/          │         │
│  └─────────────────────────────┘          └─────────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            DATABRICKS UNITY CATALOG                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │                    External Locations & Tables                   │              │
│  ├─────────────────────────────────────────────────────────────────┤              │
│  │                                                                 │              │
│  │  📍 expanso_ingestion     → s3://expanso-databricks-ingestion/  │              │
│  │  📍 expanso_validated     → s3://expanso-databricks-validated/  │              │
│  │  📍 expanso_enriched      → s3://expanso-databricks-enriched/   │              │
│  │  📍 expanso_aggregated    → s3://expanso-databricks-aggregated/ │              │
│  │  📍 expanso_checkpoints   → s3://expanso-databricks-checkpoints/│              │
│  │  📍 expanso_metadata      → s3://expanso-databricks-metadata/   │              │
│  │                                                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │                      Auto Loader Tables                         │              │
│  ├─────────────────────────────────────────────────────────────────┤              │
│  │                                                                 │              │
│  │  📊 wind_turbine_raw       (streaming from ingestion bucket)   │              │
│  │  📊 wind_turbine_validated (streaming from validated bucket)   │              │
│  │  📊 wind_turbine_enriched  (streaming from enriched bucket)    │              │
│  │  📊 wind_turbine_aggregated (streaming from aggregated bucket) │              │
│  │                                                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │                    Analytics Views & Dashboards                 │              │
│  ├─────────────────────────────────────────────────────────────────┤              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_performance_view                              │              │
│  │     Real-time performance metrics across all turbines          │              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_anomaly_detection                             │              │
│  │     Aggregated anomaly detection and alerts                    │              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_maintenance_dashboard                         │              │
│  │     Predictive maintenance insights from enriched data         │              │
│  │                                                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Details

### 1. Edge Collection (Wind Turbines)
- **1,500+ wind turbines** across 8 wind farms in 4 regions
- Each turbine runs an **Expanso node** with SQLite database
- Collects sensor data: RPM, power output, temperature, vibration, wind speed
- Data stored locally in SQLite with automatic timestamp tracking

### 2. Pipeline Processing Stages
Each Expanso node processes data through four stages:
- **ingestion**: Raw unprocessed sensor readings
- **validated**: Schema-validated data with quality checks
- **enriched**: Data enriched with Bacalhau metadata and privacy protection
- **aggregated**: Time-window aggregated data with anomaly detection

### 3. S3 Data Lake
Data is organized with:
- **Time-based partitioning**: year/month/day/hour
- **Parquet format** for efficient columnar storage
- **JSON metadata** files for each batch
- **Lifecycle policies** to move old data to cheaper storage

### 4. Databricks Unity Catalog
Provides unified access through:
- **External Locations** mapping to S3 buckets
- **Auto Loader tables** for streaming ingestion
- **Analytics views** for performance monitoring and maintenance

## Example Queries

```sql
-- Turbine performance metrics
SELECT 
  turbine_id,
  AVG(power_output) as avg_power_mw,
  AVG(efficiency) as avg_efficiency,
  MAX(temperature) as max_temp
FROM wind_turbine_aggregated
WHERE date = current_date()
GROUP BY turbine_id;

-- Anomaly detection
SELECT 
  turbine_id,
  timestamp,
  vibration_level,
  temperature,
  'High vibration detected' as alert_type
FROM wind_turbine_enriched
WHERE vibration_level > threshold_value
  AND timestamp > current_timestamp() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;

-- Maintenance planning
SELECT 
  turbine_id,
  COUNT(*) as anomaly_count,
  AVG(vibration_level) as avg_vibration,
  MAX(temperature) as max_temperature
FROM wind_turbine_validated
WHERE timestamp > current_timestamp() - INTERVAL 7 DAYS
GROUP BY turbine_id
HAVING anomaly_count > 10
ORDER BY anomaly_count DESC;
```

## Benefits of This Architecture

1. **Scalability**: Handles thousands of turbines across multiple regions
2. **Reliability**: S3 provides 99.999999999% durability
3. **Cost Efficiency**: Single region storage with lifecycle policies
4. **Real-time Analytics**: Auto Loader enables near real-time insights
5. **Data Quality**: Progressive validation and enrichment through pipeline stages
6. **Flexibility**: Four distinct pipeline stages for different processing needs
7. **Unified View**: Unity Catalog provides single pane of glass