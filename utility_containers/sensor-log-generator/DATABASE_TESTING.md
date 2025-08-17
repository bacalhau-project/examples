# Database Resilience Testing Guide

This guide provides tools and examples for testing the sensor database configuration to ensure it can handle concurrent reads and writes without corruption or data loss.

## Quick Start

### Running the Comprehensive Stress Test

```bash
# Run the full stress test suite (takes ~30 seconds)
./run_stress_test.sh
```

This will:
1. Start a sensor simulator with aggressive write settings
2. Start an external reader monitoring for new data
3. Run concurrent stress tests with multiple readers and writers
4. Validate database integrity
5. Report on any issues found

### Manual Stress Testing

```bash
# Run just the stress test with custom settings
python stress_test.py '{"num_writers": 10, "num_readers": 20, "test_duration": 60}'
```

## Safe External Reading

### Simple Example

```python
import sqlite3

# CRITICAL: Always use read-only mode for external readers
conn = sqlite3.connect(
    "file:data/sensor_data.db?mode=ro",  # Read-only mode
    uri=True,
    timeout=30.0
)
conn.execute("PRAGMA query_only=1;")  # Extra safety

# Now you can safely read while sensor is writing
cursor = conn.execute("SELECT * FROM sensor_readings ORDER BY id DESC LIMIT 10")
for row in cursor:
    print(row)

conn.close()
```

### Monitoring New Data

```bash
# Monitor for new readings every 2 seconds
python external_reader.py data/sensor_data.db --mode monitor --interval 2

# Get latest 50 readings
python external_reader.py data/sensor_data.db --mode latest --limit 50

# Get database statistics
python external_reader.py data/sensor_data.db --mode stats
```

### Simple Continuous Reader

```bash
# Run the simple example that shows incremental reading
python simple_reader_example.py
```

## Key Configuration Settings

The current configuration ensures data visibility for external readers:

### Database Settings (`src/database.py`)
- **Batch Size**: 20 readings (commits after 20 writes)
- **Batch Timeout**: 5 seconds (commits every 5 seconds regardless of batch size)
- **Journal Mode**: DELETE (compatible with cross-boundary access)
- **Synchronous**: NORMAL (balanced performance/durability)
- **Background Commit Thread**: Ensures periodic commits every 5 seconds

### Why These Settings Work

1. **DELETE Journal Mode**: Unlike WAL mode, DELETE mode doesn't use shared memory files (-shm, -wal) that can cause corruption when accessed across container boundaries.

2. **Small Batch Size (20)**: Ensures data is written frequently enough for external readers to see updates without long delays.

3. **5-Second Timeout**: Guarantees that even during low activity, data is committed regularly for external visibility.

4. **Background Commit Thread**: Provides an additional safety net to ensure commits happen even if the main thread is busy.

## Common Issues and Solutions

### Issue: "database is locked" errors
**Solution**: This is normal when the writer is committing. The 30-second timeout should handle this. If you see frequent locks, the writer might be overloaded.

### Issue: "database disk image is malformed"
**Solution**: This indicates corruption, often from using WAL mode across container boundaries. The current DELETE mode configuration prevents this.

### Issue: External readers don't see new data
**Solution**: Ensure the batch timeout is working. The background commit thread should commit every 5 seconds maximum.

### Issue: High I/O causing "disk I/O error"
**Solution**: The current configuration with `synchronous=NORMAL` and batching reduces I/O pressure while maintaining durability.

## Testing Checklist

Before deploying, run these tests:

1. ✅ **Basic Stress Test**: `./run_stress_test.sh`
   - Should show >99% success rate for reads and writes
   - Database integrity check should pass

2. ✅ **Long Duration Test**: 
   ```bash
   python stress_test.py '{"test_duration": 300, "num_writers": 5}'
   ```
   - Run for 5 minutes to catch any gradual degradation

3. ✅ **External Reader Test**:
   ```bash
   # Terminal 1: Start sensor
   python main.py --config config.yaml --identity config/identity.json
   
   # Terminal 2: Monitor with external reader
   python external_reader.py data/sensor_data.db --mode monitor
   ```
   - Should see new data within 5 seconds
   - No corruption errors

4. ✅ **Container Boundary Test**:
   ```bash
   # Start sensor in Docker
   docker run -v $(pwd)/data:/app/data sensor-simulator
   
   # Read from host
   python external_reader.py data/sensor_data.db --mode stats
   ```
   - Should work without corruption

## Performance Expectations

With the current configuration:
- **Write Throughput**: ~50-100 readings/second sustained
- **Read Latency**: <50ms for most queries
- **Data Visibility Delay**: Maximum 5 seconds
- **Concurrent Readers**: 10+ without issues
- **Database Integrity**: No corruption under normal load

## Monitoring in Production

For production use, monitor these metrics:
- Write success rate (should be >99.9%)
- Read success rate (should be >99.9%)
- Maximum batch commit time (should be <1 second)
- Database file size growth rate
- Any "disk I/O error" or "database is locked" errors in logs

## Example Integration

```python
from external_reader import SafeSensorReader

# Initialize reader
reader = SafeSensorReader("data/sensor_data.db")

# Get latest data
latest = reader.get_latest_readings(limit=100)

# Get statistics
stats = reader.get_sensor_stats()
print(f"Total readings: {stats['total_readings']}")
print(f"Anomaly rate: {stats['anomaly_rate']:.2f}%")

# Monitor continuously
def process_new_data(readings):
    for reading in readings:
        # Process each new reading
        print(f"New: {reading['sensor_id']} - {reading['temperature']}°C")

reader.monitor_continuous(process_new_data, interval=2.0)
```