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
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │ Regional Bucket │                       │ Regional Bucket │                    │
│  │   S3: us-east-1 │                       │   S3: us-west-2 │                    │
│  └─────────────────┘                       └─────────────────┘                    │
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
│  ┌─────────────────┐                       ┌─────────────────┐                    │
│  │ Regional Bucket │                       │ Regional Bucket │                    │
│  │   S3: eu-west-1 │                       │ S3: ap-southeast-1│                   │
│  └─────────────────┘                       └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           S3 DATA LAKE ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  Scenario-Based Buckets (Global)           Regional Buckets (Per Region)           │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-raw    │          │ 📦 expanso-databricks-       │         │
│  │    └── raw/                 │          │    regional-us-east-1      │         │
│  │        └── year=2024/       │          │    └── regional/          │         │
│  │            └── month=01/    │          │        └── year=2024/     │         │
│  └─────────────────────────────┘          └─────────────────────────────┘         │
│                                                                                     │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-       │          │ 📦 expanso-databricks-       │         │
│  │    filtered                 │          │    regional-us-west-2      │         │
│  │    └── filtered/            │          │    └── regional/          │         │
│  │        └── year=2024/       │          │        └── year=2024/     │         │
│  └─────────────────────────────┘          └─────────────────────────────┘         │
│                                                                                     │
│  ┌─────────────────────────────┐          ┌─────────────────────────────┐         │
│  │ 📦 expanso-databricks-       │          │ 📦 expanso-databricks-       │         │
│  │    emergency                │          │    regional-eu-west-1      │         │
│  │    └── emergency/           │          │    └── regional/          │         │
│  │        └── alerts/          │          │        └── year=2024/     │         │
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
│  │  📍 expanso_raw           → s3://expanso-databricks-raw/        │              │
│  │  📍 expanso_filtered      → s3://expanso-databricks-filtered/   │              │
│  │  📍 expanso_emergency     → s3://expanso-databricks-emergency/  │              │
│  │  📍 expanso_regional_us_east_1  → s3://expanso-.../us-east-1/  │              │
│  │  📍 expanso_regional_us_west_2  → s3://expanso-.../us-west-2/  │              │
│  │  📍 expanso_regional_eu_west_1  → s3://expanso-.../eu-west-1/  │              │
│  │  📍 expanso_regional_ap_southeast_1 → s3://expanso-.../ap-se-1/ │              │
│  │                                                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │                      Auto Loader Tables                         │              │
│  ├─────────────────────────────────────────────────────────────────┤              │
│  │                                                                 │              │
│  │  📊 wind_turbine_raw      (streaming from raw bucket)          │              │
│  │  📊 wind_turbine_filtered (streaming from filtered bucket)     │              │
│  │  📊 wind_turbine_alerts   (streaming from emergency bucket)    │              │
│  │  📊 wind_turbine_us_east  (streaming from regional bucket)     │              │
│  │  📊 wind_turbine_us_west  (streaming from regional bucket)     │              │
│  │  📊 wind_turbine_eu       (streaming from regional bucket)     │              │
│  │  📊 wind_turbine_asia     (streaming from regional bucket)     │              │
│  │                                                                 │              │
│  └─────────────────────────────────────────────────────────────────┘              │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐              │
│  │                    Cross-Region Analytics Views                 │              │
│  ├─────────────────────────────────────────────────────────────────┤              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_global_view                                   │              │
│  │     UNION ALL data from all regional tables                    │              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_performance_dashboard                         │              │
│  │     Aggregated metrics across all regions and scenarios        │              │
│  │                                                                 │              │
│  │  🔍 wind_turbine_maintenance_alerts                            │              │
│  │     Real-time alerts from emergency buckets                    │              │
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

### 2. Pipeline Processing
Each Expanso node runs the S3 uploader that:
- Detects its AWS region automatically
- Routes data based on configured pipeline type:
  - **raw**: Unprocessed sensor readings
  - **filtered**: Anomaly detection (high vibration, temperature)
  - **emergency**: Critical alerts requiring immediate action
  - **regional**: Region-specific routing for compliance/latency

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
- **Cross-region views** for global analytics

## Example Queries

```sql
-- Global turbine performance
SELECT 
  region,
  COUNT(DISTINCT turbine_id) as turbine_count,
  AVG(power_output) as avg_power_mw,
  AVG(efficiency) as avg_efficiency
FROM wind_turbine_global_view
WHERE date = current_date()
GROUP BY region;

-- Maintenance alerts by region
SELECT 
  region,
  turbine_id,
  alert_type,
  severity,
  timestamp
FROM wind_turbine_maintenance_alerts
WHERE severity = 'CRITICAL'
  AND timestamp > current_timestamp() - INTERVAL 1 HOUR
ORDER BY timestamp DESC;

-- Regional compliance reporting
SELECT 
  date_trunc('day', timestamp) as day,
  COUNT(*) as reading_count,
  SUM(power_output) as total_power_mwh
FROM wind_turbine_eu
WHERE country_code IN ('DE', 'FR', 'ES')
GROUP BY 1
ORDER BY 1;
```

## Benefits of This Architecture

1. **Scalability**: Handles thousands of turbines across multiple regions
2. **Reliability**: S3 provides 99.999999999% durability
3. **Cost Efficiency**: Regional buckets minimize data transfer costs
4. **Real-time Analytics**: Auto Loader enables near real-time insights
5. **Compliance**: Regional data isolation for regulatory requirements
6. **Flexibility**: Multiple pipeline types for different use cases
7. **Unified View**: Unity Catalog provides single pane of glass