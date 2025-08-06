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
    │   🪣 us-east-1 bucket      🪣 us-west-2 bucket            │
    │                                                              │
    │   🌬️ Wind Farm EU           🌬️ Wind Farm Asia             │
    │   ┌─────────────────┐      ┌─────────────────┐            │
    │   │ 525 Turbines    │      │ 250 Turbines    │            │
    │   │ w/ Expanso      │      │ w/ Expanso      │            │
    │   └────────┬────────┘      └────────┬────────┘            │
    │            │                         │                      │
    │            │ SQLite ──► S3          │ SQLite ──► S3        │
    │            ▼                         ▼                      │
    │   🪣 eu-west-1 bucket      🪣 ap-southeast-1 bucket       │
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
    │              🌐 Unified View Across All Regions              │
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

### 2️⃣ Smart Data Routing
```
Pipeline Manager decides:
    ↓
┌─────────────────────────────┐
│ 🟢 Normal → "raw" bucket    │
│ 🟡 Filtered → "filtered"    │
│ 🔴 Emergency → "emergency"  │
│ 🌍 Regional → region bucket │
└─────────────────────────────┘
    ↓
📤 Upload to S3
(Parquet format, partitioned by time)
```

### 3️⃣ Unified Analytics
```
S3 Buckets (distributed globally)
    ↓
🔄 Databricks Auto Loader
(Continuous streaming ingestion)
    ↓
📊 Unity Catalog Tables
    ↓
┌─────────────────────────────┐
│ SELECT region, AVG(power)   │
│ FROM turbine_global_view    │
│ WHERE date = today()        │
└─────────────────────────────┘
```

## Key Numbers

| Component | Count | Details |
|-----------|-------|---------|
| 🌬️ Wind Turbines | 1,425 | Across 8 wind farms |
| 🌍 Regions | 4 | US-East, US-West, EU, Asia |
| 🪣 S3 Buckets | 8 | 4 regional + 4 scenario-based |
| 📊 Data Points | ~20M/day | Per turbine: 14 metrics/min |
| ⚡ Latency | <5 min | From sensor to dashboard |

## Benefits

✅ **Local First**: Data stays close to source  
✅ **Resilient**: Works offline, syncs when connected  
✅ **Scalable**: Add turbines without central bottleneck  
✅ **Cost Effective**: Regional storage reduces transfer costs  
✅ **Compliant**: Data sovereignty by region  
✅ **Real-time**: Streaming analytics with Auto Loader