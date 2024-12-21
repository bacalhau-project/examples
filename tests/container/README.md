# Container Orchestration Tests

Tests to verify container connectivity and functionality across platforms.

## Running Tests
```bash
pytest tests/container/
```

## Platform-specific Considerations
- Mac: Uses $DOCKER_HOST if set
- Linux: Uses default /var/run/docker.sock
