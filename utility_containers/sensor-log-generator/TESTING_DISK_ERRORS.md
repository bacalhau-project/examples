# Testing Disk I/O Error Resilience

This guide explains how to test and reproduce disk I/O errors that commonly occur in production containerized environments.

## Overview

The sensor simulator now includes resilient write mechanisms to handle disk I/O errors gracefully:
- **In-memory failure buffer** - Failed writes are kept in memory
- **Smart retry sequence** - Retries at 1s, 3s, 5s, 9s, 12s, 15s (then every 15s)
- **Error suppression** - No ERROR logs until after 15-second retry fails
- **Recovery file generation** - Unwritten data is saved on shutdown
- **Zero data loss** - System continues operating during disk errors

### Error Logging Behavior
The system uses intelligent error suppression to prevent log spam:
- **First 5 retries (1s-12s)**: Uses INFO/DEBUG logging only
- **After 15-second retry**: Logs as ERROR if still failing
- **Recovery**: Always logged as INFO when data is successfully written

This means transient issues (< 15 seconds) won't clutter your error logs, but persistent problems will be properly flagged.

## Quick Start

### 1. Python Simulation Script
```bash
# Interactive test menu with multiple scenarios
uv run simulate_disk_errors.py

# Run specific test
uv run test_resilient_writes.py
```

### 2. Docker Stress Tests
```bash
# Run comprehensive production stress test
./stress_test_production.sh

# Individual stress scenarios
docker-compose -f docker-compose.stress.yml up sensor-limited-memory
docker-compose -f docker-compose.stress.yml up sensor-readonly
docker-compose -f docker-compose.stress.yml up sensor-chaos
```

## Common Production Issues Simulated

### 1. Read-Only Filesystem
**Symptoms:** "Read-only file system" errors  
**Common Causes:**
- Container filesystem corruption
- Docker daemon issues
- Host filesystem remounted as read-only
- Kubernetes pod eviction/migration

**Test Method:**
```bash
# Make database read-only during operation
chmod 444 data/sensor_data.db
sleep 10
chmod 644 data/sensor_data.db
```

### 2. Disk Full Errors
**Symptoms:** "No space left on device"  
**Common Causes:**
- Container size limits reached
- Host disk full
- Docker overlay storage exhausted
- Log rotation failure

**Test Method:**
```bash
# Use tmpfs with size limit
docker run -v /app/data --tmpfs /app/data:size=10M sensor-simulator
```

### 3. Intermittent I/O Errors
**Symptoms:** Random "disk I/O error" messages  
**Common Causes:**
- Network storage latency (NFS/EFS)
- Docker volume driver issues
- Container resource throttling
- Simultaneous container operations

**Test Method:**
```python
# Python script randomly toggles permissions
with sim.intermittent_errors(error_rate=0.3, duration=30):
    # Run sensor simulation
```

### 4. Container Restarts
**Symptoms:** Data loss after container restart  
**Common Causes:**
- OOM kills
- Health check failures
- Orchestrator rescheduling
- Manual restarts

**Test Method:**
```bash
# Chaos monkey kills container periodically
while true; do
    sleep $(( RANDOM % 60 + 30 ))
    docker kill sensor-chaos
done
```

## Monitoring Failure Buffer

### Check Buffer Status
```python
# In your monitoring code
stats = database.get_database_stats()
failure_buffer_size = stats["performance_metrics"]["failure_buffer_size"]

if failure_buffer_size > 1000:
    alert("High failure buffer size: {}".format(failure_buffer_size))
```

### Log Analysis
Look for these patterns in logs:
```
ERROR - DISK I/O ERROR - Buffering reading in memory for later retry
INFO - Added reading to failure buffer (current size: 42)
INFO - Attempting to retry 42 failed writes (retry #3, interval: 33.8s)
INFO - Successfully wrote 42 readings from failure buffer
```

## Resource-Constrained Testing

### Memory Limits
```yaml
# docker-compose.stress.yml
deploy:
  resources:
    limits:
      memory: 50M  # Extreme limit to test OOM handling
```

### CPU Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '0.1'  # Minimal CPU to test throttling
```

### I/O Limits
```yaml
blkio_config:
  device_write_bps:
    - path: /dev/sda
      rate: '100kb'  # Extremely slow I/O
```

## Performance Impact

### Normal Operation
- Write latency: ~1-5ms per reading
- Batch commits: Every 20 readings or 5 seconds
- Memory usage: ~50-100MB baseline

### During I/O Errors
- Failure buffer grows: ~1KB per reading
- Max buffer size: 10,000 readings (~10MB)
- Retry intervals: 1s → 3s → 5s → 9s → 12s → 15s (then stays at 15s)
- Recovery time: Typically < 20 seconds after issue resolved

## Best Practices

### 1. Configure Appropriate Limits
```python
# In database.py
self.failure_buffer_max_size = 10000  # Adjust based on memory
self.failure_buffer_retry_intervals = [1.0, 3.0, 5.0, 9.0, 12.0, 15.0]  # Custom retry sequence
self.failure_buffer_max_retry_interval = 15.0  # Max 15 seconds between retries
```

### 2. Monitor Key Metrics
- `failure_buffer_size` - Current buffered readings
- `disk_io_errors` - Count of I/O errors
- `retry_attempts` - Number of retry attempts
- `data_loss` - Any readings that couldn't be saved

### 3. Set Up Alerts
```yaml
# Example Prometheus alert
- alert: HighFailureBuffer
  expr: sensor_failure_buffer_size > 5000
  for: 5m
  annotations:
    summary: "High failure buffer size ({{ $value }} readings)"
```

### 4. Recovery Procedures
1. Check disk space: `df -h /data`
2. Check permissions: `ls -la /data/sensor_data.db`
3. Check container resources: `docker stats`
4. Review logs: `docker logs sensor-container | grep ERROR`
5. Check recovery file: `ls /data/*_recovery.json`

## Troubleshooting

### Issue: Continuous "disk I/O error" messages
**Solution:**
1. Check host disk space: `df -h`
2. Check Docker space: `docker system df`
3. Clean up: `docker system prune -a`
4. Check volume mounts: `docker inspect container_name | grep Mounts`

### Issue: Failure buffer keeps growing
**Solution:**
1. Database file may be corrupted
2. Try moving/renaming old database
3. Container will create fresh database
4. Old data in recovery JSON file

### Issue: High memory usage
**Solution:**
1. Reduce `failure_buffer_max_size`
2. Decrease `batch_size` for more frequent commits
3. Increase container memory limits

## Testing Checklist

- [ ] Normal operation baseline established
- [ ] Read-only filesystem handled gracefully
- [ ] Disk full scenarios tested
- [ ] Intermittent errors don't cause data loss
- [ ] Container restarts preserve data
- [ ] High-frequency writes work under pressure
- [ ] Memory limits don't cause crashes
- [ ] Recovery files generated on failure
- [ ] Monitoring metrics are accurate
- [ ] Logs provide sufficient debugging info

## Automated Testing

Run the full test suite:
```bash
# All automated tests
make test-resilience

# Or manually
uv run pytest tests/test_database.py -k resilient
uv run simulate_disk_errors.py
./stress_test_production.sh
```

## Support

If you encounter persistent disk I/O errors in production:
1. Collect logs: `docker logs container > sensor_logs.txt`
2. Check recovery files: `ls -la data/*_recovery.json`
3. Get database stats: `sqlite3 data/sensor_data.db ".dbstat"`
4. Open issue with logs and configuration