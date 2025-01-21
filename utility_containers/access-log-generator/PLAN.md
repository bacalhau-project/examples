# Access Log Generator Improvement Plan

## Current State Analysis

The access-log-generator has a sophisticated implementation with:

1. Advanced user behavior simulation:
   - State machine for user sessions (START, LOGIN, BROWSING, etc.)
   - Realistic page navigation patterns
   - Session abandonment logic
   - Error scenarios (404s, 500s, etc.)
   - Traffic pattern multipliers

2. Robust infrastructure:
   - Custom log rotation handler with size and time-based rotation
   - Atomic writes with retry logic
   - Separate logging streams for access and errors
   - Proper error handling and recovery

3. Comprehensive configuration:
   - YAML config file support with validation
   - Configurable state transitions
   - Adjustable error rates
   - Traffic pattern configuration
   - Session duration parameters

## Goals for Access Log Generator

1. Simulate realistic user behavior:
   - Login/logout sequences
   - Page navigation patterns
   - Session abandonment
   - Error scenarios (404s, 403s)
   
2. Maintain clean infrastructure:
   - Proper Docker setup
   - Log rotation
   - Atomic writes
   - Error handling

3. Generate useful metrics:
   - Session duration
   - Page views per session
   - Error rates
   - Popular pages

## Implementation Plan

### 0. Initial Cleanup
- [x] Delete unused files:
```bash
rm -rf bacalhau.service ipfs.service start_bacalhau.sh
```
- [x] Reorganize directory structure:
```bash
mkdir -p {logs,config,tests} && mv tools/log-generator/* . && rm -rf tools
```

### 1. Core Log Generation
- [x] Implemented in `access_log_generator.py` with:
  - [x] Sophisticated user session simulation via state machine
  - [x] Realistic page navigation patterns with query parameters
  - [x] Configurable error scenario injection
  - [x] Atomic file writes with retry logic
  - [x] Custom log rotation handler
  - [x] Separate logging streams for access and errors

### 2. Docker Infrastructure
- [x] Create Dockerfile with:
  - [x] Non-root user
  - [x] Log rotation
  - [x] Proper permissions
  - [x] Health checks
  - [x] Volume mounts

### 3. User Behavior Simulation
- [x] Implemented sophisticated state machine:
```
Start -> Login -> Browsing -> (Logout | Abandon | Error)
       -> Direct Access -> Browsing -> (Leave | Error)
```
- [x] Realistic page navigation with:
  - Query parameter generation
  - Referrer tracking
  - Session duration control
  - Configurable transition probabilities

### 5. Error Handling
- [x] Implemented robust error handling for:
  - File I/O with retry logic
  - Log rotation failures
  - State transition errors
  - Configuration validation
  - Write failures with recovery

### 6. Configuration
- [x] Implemented comprehensive configuration via YAML:
  - [x] Traffic patterns with time-based multipliers
  - [x] Error rates (404, 500, etc.)
  - [x] Session duration parameters
  - [x] State transition probabilities
  - [x] Navigation path weights
  - [x] Validation of configuration values

### 7. Testing
- [ ] Add unit tests for:
  - Log format validation
  - User behavior simulation
  - Error handling
  - File operations

### 8. Documentation
- [ ] Add README.md with:
  - Usage instructions
  - Configuration options
  - Example outputs
  - Troubleshooting guide

## Timeline

1. Week 1: Core log generation and Docker setup
2. Week 2: User behavior simulation and error handling
3. Week 3: Testing and documentation
4. Week 4: Final polish and performance tuning

## Success Metrics

1. Realistic user behavior simulation
2. Stable log generation at scale
3. Proper error handling and recovery
4. Clean, maintainable codebase
5. Comprehensive documentation

## Testing Commands

To test the log generator in another terminal:
```bash
# Build and run the container
docker build -t access-log-gen . && docker run -it --rm -v $(pwd)/logs:/app/output access-log-gen --rate 5

# Tail the output logs
tail -f logs/generated.log
```

## Directory Structure

```
access-log-generator/
├── Dockerfile
├── README.md
├── access_log_generator.py
├── config/
│   └── logrotate.conf
├── logs/
├── requirements.txt
├── tests/
│   └── test_access_log_generator.py
└── utils/
    ├── __init__.py
    ├── file_utils.py
    ├── log_utils.py
    └── user_simulator.py
```

## Key Components

1. **User Simulation**:
   - Random walk through pages
   - Login/logout sequences
   - Session timeouts
   - Error scenarios

2. **Log Format**:
   - Common Log Format (CLF) compatible
   - Extended fields for analytics
   - JSON output option

3. **Configuration**:
   - Traffic patterns (peak/off-peak)
   - Error rates
   - User distribution
   - Session lengths

4. **Infrastructure**:
   - Docker container
   - Log rotation
   - Health checks
   - Resource limits
