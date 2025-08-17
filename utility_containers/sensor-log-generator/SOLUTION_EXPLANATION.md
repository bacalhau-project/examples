# SQLite WAL Mode Data Persistence Solution

## Problem Analysis

The original code suffered from data loss when the Docker container was stopped with `docker stop` because:

1. **SIGTERM Signal Handling**: Docker sends SIGTERM to the container's main process when stopped, giving it 10 seconds to shut down gracefully before sending SIGKILL
2. **WAL Mode Behavior**: SQLite's Write-Ahead Logging keeps recent writes in a separate `.wal` file that must be checkpointed to the main database
3. **Missing Checkpoint**: The original `try...finally` block couldn't catch SIGTERM, so the WAL checkpoint never happened

## Solution Components

### 1. Signal Handler Registration
```python
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```
- Catches SIGTERM from `docker stop`
- Catches SIGINT from Ctrl+C
- Sets a shutdown flag to exit the main loop gracefully

### 2. Explicit WAL Checkpoint Management
```python
def checkpoint(self, mode="PASSIVE"):
    result = self.conn.execute(f"PRAGMA wal_checkpoint({mode});").fetchone()
```

The solution implements four checkpoint modes:
- **PASSIVE**: Non-blocking, checkpoints what it can
- **FULL**: Waits for exclusive lock, checkpoints all frames
- **RESTART**: Like FULL, also restarts WAL for next transaction
- **TRUNCATE**: Like RESTART, also truncates WAL file (used on shutdown)

### 3. Periodic Checkpointing
```python
if current_time - self.last_checkpoint_time > self.checkpoint_interval:
    self.checkpoint()
```
- Performs periodic checkpoints every 60 seconds
- Ensures data is regularly persisted even during long runs

### 4. Final Cleanup with TRUNCATE Checkpoint
```python
def close(self):
    # Force a TRUNCATE checkpoint for maximum durability
    result = self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
```
- Executes the most aggressive checkpoint mode on shutdown
- Ensures ALL data from WAL is written to main database
- Cleans up WAL and SHM files

### 5. Thread-Safe Database Operations
```python
class DatabaseManager:
    def __init__(self, db_path):
        self.lock = Lock()
```
- Uses locks to ensure thread-safe database access
- Prevents race conditions during checkpoint operations

### 6. Optimized SQLite Settings
```python
"PRAGMA synchronous=NORMAL;",      # Balance safety and speed
"PRAGMA wal_autocheckpoint=1000;", # Auto-checkpoint every 1000 pages
"PRAGMA busy_timeout=5000;",       # 5 second timeout for locks
```
- Maintains high throughput with WAL mode
- Configures automatic checkpointing
- Sets appropriate timeouts for containerized environments

## Key Improvements Over Original

1. **Signal Handling**: Properly catches and responds to SIGTERM
2. **Explicit Checkpointing**: Forces data persistence before exit
3. **Monitoring**: Logs checkpoint statistics and operation status
4. **Error Recovery**: Handles database errors gracefully
5. **Statistics**: Tracks readings generated and error rates
6. **Environment Awareness**: Reads configuration from environment variables

## Testing the Solution

### Test 1: Foreground Mode (Should Already Work)
```bash
docker run -v $(pwd)/data:/app/data sensor-app
# Press Ctrl+C
# Check: data should be saved
```

### Test 2: Detached Mode (Previously Failed)
```bash
docker run -d --name test-sensor -v $(pwd)/data:/app/data sensor-app
sleep 30  # Let it generate some data
docker stop test-sensor
# Check: ALL data should be saved
```

### Test 3: Verify Data Persistence
```bash
sqlite3 data/sensor_data.db "SELECT COUNT(*) FROM sensor_readings;"
# Should show the exact count of generated readings
```

## Performance Considerations

The solution maintains high throughput by:
- Keeping WAL mode enabled for concurrent writes
- Using NORMAL synchronous mode during operation
- Only using FULL synchronous mode during final shutdown
- Batching writes within transactions
- Using memory for temporary storage

## Container-Specific Optimizations

1. **Directory Creation**: Ensures `/app/data` exists before writing
2. **Timeout Settings**: Appropriate for container environments
3. **Signal Handling**: Works with Docker's shutdown sequence
4. **Logging**: Comprehensive logging for debugging in containers

## Explanation of Changes

### Why the Original try...finally Was Insufficient

The original code's `try...finally` block only catches Python exceptions and KeyboardInterrupt. It does NOT catch Unix signals like SIGTERM. When Docker sends SIGTERM, Python's default behavior is to immediately terminate, bypassing the finally block entirely.

### How Signal Handling Solves This

By registering a signal handler for SIGTERM, we intercept Docker's shutdown signal and convert it into a controlled shutdown sequence:

1. Signal received → Set shutdown flag
2. Main loop checks flag → Exits gracefully
3. Cleanup code runs → Executes WAL checkpoint
4. Database closed → All data persisted

### The Critical SQLite PRAGMA Command

`PRAGMA wal_checkpoint(TRUNCATE)` is the key to guaranteeing data persistence:
- Forces all WAL frames to be written to the main database
- Waits for exclusive access to ensure completion
- Truncates the WAL file after successful checkpoint
- Guarantees that the `.db` file contains ALL data

This ensures that even if the container is destroyed immediately after our process exits, all data has already been safely written to the persistent volume.

## Summary

This solution successfully maintains the performance benefits of WAL mode while ensuring complete data persistence when containers are stopped. The key insight is that containerized applications must explicitly handle SIGTERM signals and force SQLite checkpoints to guarantee data durability.