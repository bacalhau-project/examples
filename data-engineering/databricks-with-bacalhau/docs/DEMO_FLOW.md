# Databricks with Bacalhau - Demo Flow

## Overview
This demo showcases the evolution of data from raw sensor readings through increasingly sophisticated processing stages, demonstrating key data engineering concepts at each step.

## Demo Flow Stages

### Stage 1: Data Ingestion
**What it shows**: Baseline data capture without processing
- **Processing**: Direct SQLite → S3 upload as raw text/JSON
- **S3 Bucket**: `expanso-databricks-ingestion-{region}`
- **Key Point**: Fast, simple ingestion preserving all original data
- **Visual**: Show raw JSON files in S3 bucket with nested date partitions
- **Command**: 
  ```bash
  uv run -s pipeline_manager.py --db sensor_data.db set --type ingestion --by "demo_user"
  uv run -s s3_autoloader_landing_service.py
  ```

### Stage 2: Data Validation
**What it shows**: Data quality enforcement at ingestion
- **Processing**: 
  - Enforce schema with proper data types
  - Validate ranges (temperature, humidity, etc.)
  - Add validation metadata (pass/fail, error details)
- **S3 Bucket**: `expanso-databricks-validated-{region}`
- **Key Point**: Catch data quality issues early
- **Visual**: Show schema enforcement in Databricks table, highlight rejected records
- **Command**:
  ```bash
  uv run -s pipeline_manager.py --db sensor_data.db set --type validated --by "demo_user"
  ```

### Stage 3: Metadata Enrichment & Privacy
**What it shows**: Processing transparency and traceability
- **Processing**:
  - Add Bacalhau job metadata (job_id, node_id, execution_time)
  - Capture node snapshot (CPU, memory, GPU, capabilities, location)
  - Add data lineage (source_file, processing_timestamp, pipeline_version)
  - GPS fuzzing for privacy protection
- **S3 Bucket**: `expanso-databricks-enriched-{region}`
- **Key Point**: Full traceability from edge to warehouse + privacy protection
- **Visual**: Query showing node capabilities and processing distribution
- **Command**:
  ```bash
  uv run -s pipeline_manager.py --db sensor_data.db set --type enriched --by "demo_user"
  ```

### Stage 4: Edge Aggregation & Anomaly Detection
**What it shows**: Distributed compute before data movement
- **Processing**:
  - Time-window aggregations (5-min averages)
  - Anomaly detection at edge
  - Data volume reduction (90% reduction)
  - Alert prioritization (high/medium/low)
- **S3 Bucket**: `expanso-databricks-aggregated-{region}`
- **Key Point**: Reduce data movement costs and latency
- **Visual**: 
  - Show original vs reduced data volumes
  - Real-time anomaly dashboard
  - Cost savings calculation
- **Command**:
  ```bash
  uv run -s pipeline_manager.py --db sensor_data.db set --type aggregated --by "demo_user"
  ```

### Stage 5: Real-time Alerting
**What it shows**: Immediate action on critical data
- **Processing**:
  - Filter for anomalies and critical events
  - Route emergency data to dedicated stream
  - Trigger downstream alerts
- **Key Point**: Edge computing enables real-time response
- **Visual**: Dashboard showing alert latency (edge vs cloud processing)

## Key Demo Points

### 1. **Progressive Data Enhancement**
Show how each stage adds value while preserving the ability to reprocess from raw data.

### 2. **Edge Computing Benefits**
- **Latency**: Process data where it's generated
- **Bandwidth**: 90% reduction in data transfer
- **Cost**: Lower egress and storage costs
- **Privacy**: GPS fuzzing happens at source

### 3. **Distributed Pipeline Advantages**
- **Scalability**: Process TB of data across 1000s of edge nodes
- **Reliability**: No single point of failure
- **Flexibility**: Different processing for different data types

### 4. **Bacalhau Integration**
- Show Bacalhau job metadata in final tables
- Demonstrate job distribution across nodes
- Query performance by compute location

## Demo Queries

### 1. Data Volume Reduction
```sql
SELECT 
  pipeline_type,
  COUNT(*) as record_count,
  SUM(data_size) as total_bytes,
  AVG(processing_time) as avg_process_time
FROM sensor_data.pipeline_metrics
GROUP BY pipeline_type
ORDER BY pipeline_type;
```

### 2. Edge vs Cloud Processing Latency
```sql
SELECT 
  processing_location,
  AVG(end_to_end_latency) as avg_latency,
  PERCENTILE(end_to_end_latency, 0.95) as p95_latency
FROM sensor_data.latency_metrics
WHERE timestamp > current_timestamp() - INTERVAL 1 HOUR
GROUP BY processing_location;
```

### 3. Bacalhau Node Performance & Capabilities
```sql
-- Show node performance with hardware capabilities
SELECT 
  bm.node_id,
  bm.node_snapshot.node_type,
  bm.node_snapshot.cpu_cores,
  bm.node_snapshot.memory_gb,
  bm.node_snapshot.gpu_count,
  bm.node_snapshot.capabilities,
  bm.node_snapshot.location.city as city,
  bm.node_snapshot.location.datacenter as datacenter,
  COUNT(DISTINCT bm.job_id) as jobs_processed,
  COUNT(*) as records_processed,
  AVG(bm.execution_time_ms) as avg_execution_ms,
  MIN(bm.execution_time_ms) as min_execution_ms,
  MAX(bm.execution_time_ms) as max_execution_ms
FROM sensor_data.sensor_readings_enriched
LATERAL VIEW explode(_bacalhau_metadata) AS bm
WHERE _bacalhau_metadata IS NOT NULL
GROUP BY 
  bm.node_id, bm.node_snapshot.node_type, bm.node_snapshot.cpu_cores,
  bm.node_snapshot.memory_gb, bm.node_snapshot.gpu_count,
  bm.node_snapshot.capabilities, bm.node_snapshot.location.city,
  bm.node_snapshot.location.datacenter
ORDER BY records_processed DESC;
```

### 4. GPS Privacy Protection
```sql
-- Show GPS fuzzing in action
SELECT 
  sensor_id,
  original_latitude,
  original_longitude,
  latitude as fuzzy_latitude,
  longitude as fuzzy_longitude,
  ROUND(
    111111 * SQRT(
      POWER(original_latitude - latitude, 2) + 
      POWER(original_longitude - longitude, 2)
    ), 2
  ) as fuzzing_distance_meters,
  _privacy.fuzzing_radius_km,
  _privacy.fuzzing_timestamp
FROM sensor_data.sensor_readings_enriched
WHERE _privacy.gps_fuzzed = true
LIMIT 10;
```

### 5. Geographic Distribution of Edge Processing
```sql
-- Show where data is being processed globally
SELECT 
  _bacalhau_metadata.node_snapshot.location.country as country,
  _bacalhau_metadata.node_snapshot.location.city as city,
  _bacalhau_metadata.node_snapshot.location.datacenter as datacenter,
  COUNT(DISTINCT _bacalhau_metadata.node_id) as unique_nodes,
  COUNT(DISTINCT _bacalhau_metadata.job_id) as unique_jobs,
  COUNT(*) as records_processed,
  AVG(_bacalhau_metadata.execution_time_ms) as avg_latency_ms,
  SUM(CASE WHEN anomaly_flag = 1 THEN 1 ELSE 0 END) as anomalies_detected
FROM sensor_data.sensor_readings_enriched
WHERE _bacalhau_metadata IS NOT NULL
GROUP BY 
  _bacalhau_metadata.node_snapshot.location.country,
  _bacalhau_metadata.node_snapshot.location.city,
  _bacalhau_metadata.node_snapshot.location.datacenter
ORDER BY records_processed DESC;
```

## Implementation Components

### 1. Enhanced Transformer
Add these capabilities to the data transformer:
- Schema validation with detailed error reporting
- Bacalhau metadata injection
- GPS fuzzing algorithm
- Time-window aggregation
- Anomaly detection scoring

### 2. Pipeline Manager Extensions
- Track data volume metrics
- Record processing location (edge vs cloud)
- Measure end-to-end latency
- Store Bacalhau job metadata

### 3. Monitoring Dashboard
Create Databricks dashboard showing:
- Data volume by pipeline stage
- Processing latency comparison
- Geographic distribution of sensors
- Anomaly detection rates
- Cost savings metrics

## Success Metrics

1. **Data Reduction**: Show 90%+ reduction from raw to aggregated
2. **Latency Improvement**: Edge processing 10x faster than cloud-only
3. **Cost Savings**: 80% reduction in data transfer costs
4. **Privacy Compliance**: 100% of GPS data properly fuzzed
5. **Anomaly Detection**: <1 second from event to alert

This demo flow progressively showcases the value of distributed data processing, making it clear why processing at the edge with Bacalhau provides significant advantages over traditional centralized approaches.