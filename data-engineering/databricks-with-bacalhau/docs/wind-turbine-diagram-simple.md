# Wind Turbine Data Pipeline - Simplified View

## High-Level Architecture

```
                     🌍 GLOBAL WIND TURBINE FLEET 🌍
    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │   🌬️ Wind Farm US-East      🌬️ Wind Farm US-West           │
    │   ┌─────────────────┐      ┌─────────────────┐            │
    │   │ 325 Turbines    │      │ 325 Turbines    │            │
    │   │ w/ Expanso      │      │ w/ Expanso      │            │
    │   └────────┬────────┘      └────────┬────────┘            │
    │            │                         │                      │
    │            │ SQLite ──► S3          │ SQLite ──► S3        │
    │            ▼                         ▼                      │
    │                                                              │
    │   🌬️ Wind Farm EU           🌬️ Wind Farm Asia             │
    │   ┌─────────────────┐      ┌─────────────────┐            │
    │   │ 525 Turbines    │      │ 250 Turbines    │            │
    │   │ w/ Expanso      │      │ w/ Expanso      │            │
    │   └────────┬────────┘      └────────┬────────┘            │
    │            │                         │                      │
    │            │ SQLite ──► S3          │ SQLite ──► S3        │
    │            ▼                         ▼                      │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
                                   │
                                   │ 4-Stage Pipeline
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    S3 DATA PIPELINE STAGES                   │
    │                                                              │
    │   📦 Ingestion ──► 📦 Validated ──► 📦 Enriched ──► 📦 Aggregated │
    │   (Raw data)     (Quality checks)  (Metadata)    (Analytics) │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘
                                   │
                                   │ Auto Loader
                                   ▼
    ┌──────────────────────────────────────────────────────────────┐
    │                    DATABRICKS UNITY CATALOG                  │
    │                                                              │
    │   📊 Global Analytics        🔍 Real-time Monitoring        │
    │   ┌─────────────────┐      ┌─────────────────┐            │
    │   │ • Performance   │      │ • Alerts        │            │
    │   │ • Efficiency    │      │ • Maintenance   │            │
    │   │ • Production    │      │ • Anomalies     │            │
    │   └─────────────────┘      └─────────────────┘            │
    │                                                              │
    │              🌐 Unified View Across All Turbines             │
    └──────────────────────────────────────────────────────────────┘
```

## How It Works

### 1️⃣ Data Collection at the Edge
```
Each Wind Turbine
    ↓
📊 Sensors measure:
• RPM, Power Output
• Temperature, Vibration
• Wind Speed, Direction
    ↓
💾 SQLite Database
(Local storage on turbine)
    ↓
🚀 Expanso Node
(Runs data pipeline)
```

### 2️⃣ Progressive Data Processing
```
Pipeline stages process data:
    ↓
┌─────────────────────────────┐
│ 1. Ingestion: Raw data      │
│ 2. Validated: Quality checks│
│ 3. Enriched: Add metadata   │
│ 4. Aggregated: Analytics    │
└─────────────────────────────┘
    ↓
📤 Upload to S3
(Parquet format, partitioned by time)
```

### 3️⃣ Unified Analytics
```
S3 Buckets (4 pipeline stages)
    ↓
🔄 Databricks Auto Loader
(Continuous streaming ingestion)
    ↓
📊 Unity Catalog Tables
    ↓
┌─────────────────────────────┐
│ SELECT turbine_id, AVG(power)│
│ FROM wind_turbine_aggregated │
│ WHERE date = today()        │
└─────────────────────────────┘
```

## Key Numbers

| Component | Count | Details |
|-----------|-------|---------|
| 🌬️ Wind Turbines | 1,425 | Across 8 wind farms |
| 🌍 Regions | 4 | US-East, US-West, EU, Asia |
| 🪣 S3 Buckets | 6 | 4 pipeline stages + 2 support |
| 📊 Data Points | ~20M/day | Per turbine: 14 metrics/min |
| ⚡ Latency | <5 min | From sensor to dashboard |

## Pipeline Stages Explained

| Stage | Purpose | Processing |
|-------|---------|------------|
| **Ingestion** | Raw sensor data | Direct upload from edge |
| **Validated** | Quality assurance | Schema validation, range checks |
| **Enriched** | Enhanced data | Add Bacalhau metadata, privacy filters |
| **Aggregated** | Analytics-ready | Time windows, anomaly scores |

## Benefits

✅ **Local First**: Data stays close to source  
✅ **Progressive Enhancement**: Data quality improves through pipeline  
✅ **Scalable**: Add turbines without central bottleneck  
✅ **Cost Effective**: Single region storage with lifecycle policies  
✅ **Real-time**: Streaming analytics with Auto Loader  
✅ **Simple**: Clean 4-stage pipeline without complexity