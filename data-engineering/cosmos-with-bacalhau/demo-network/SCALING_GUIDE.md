# Bacalhau Scaling Optimization Guide

This document outlines the efforts and optimizations made to scale Bacalhau for high-density demo environments, including the reasoning behind each decision to help future engineers continue this work.

## Current Setup

- **Hardware:** 40 CPU cores, 251GB RAM
- **Goal:** Run up to 600 Bacalhau compute nodes and 600 jobs (1,200 containers total)
- **Docker Compose:** Updated to support both DinD and host-Docker nodes

## Key Optimizations Made

### 1. Network Architecture Changes

- **Changed orchestrator to use host network mode**
    - **Reasoning:** The orchestrator is a central component that needs to handle connections from all compute nodes. Using host network mode eliminates Docker's network address translation overhead, reduces latency, and prevents port conflicts when scaling to hundreds of nodes.

- **Added ability to run non-DinD nodes that share the host Docker daemon**
    - **Reasoning:** Docker-in-Docker (DinD) nodes are resource-intensive as each runs its own Docker daemon. Each DinD node must independently pull images and manage its own container lifecycle. By mounting the host Docker socket, we can run more nodes with fewer resources since they share a single Docker daemon instance.

- **Added proper labels to differentiate between node types (`docker-type=dind` vs `docker-type=host`)**
    - **Reasoning:** Labels allow targeting specific node types for jobs, enabling flexible testing and deployment strategies. This helps with debugging and understanding system behavior at scale.

### 2. System Optimization Script

Created an optimization script (`optimize-for-containers.sh`) that configures:

- **File descriptor limits (1M)**
    - **Reasoning:** Each container and network connection consumes file descriptors. Default limits (1024) are quickly exhausted when running hundreds of containers.

- **Process limits (1M)**
    - **Reasoning:** Each container spawns multiple processes. The default process limits become a bottleneck when scaling beyond a few hundred containers. This was the root cause of the cgroup errors encountered.

- **Kernel parameters for heavy container workloads**
    - **Reasoning:** Default kernel settings for networking, memory, and process management are tuned for general-purpose computing, not for dense container deployments. These optimizations prevent resource exhaustion.

- **Docker daemon configuration**
    - **Reasoning:** Custom Docker settings with proper ulimits, network pools, and cgroup settings allow Docker to manage many containers efficiently without hitting system limits.

- **Systemd and cgroup v2 settings**
    - **Reasoning:** Modern Linux distributions use cgroup v2, which requires explicit configuration to handle very large numbers of containers. The systemd configuration ensures Docker service has sufficient task limits.

### 3. Benchmark Jobs

Developed benchmark jobs to establish baselines:

- **`benchmark-light.yaml`: Lightweight CPU/IO workload (~15 seconds)**
    - **Reasoning:** A lightweight job allows testing the maximum number of nodes that can be deployed without consuming excessive resources. The short duration (15s) enables rapid testing cycles.

- **`benchmark-pull.yaml`: Pre-pulls images to reduce startup time**
    - **Reasoning:** Image pulling creates significant network and disk I/O load when scaled to hundreds of nodes. Pre-pulling helps isolate execution issues from image distribution issues.

- **Decoupling scaling tests from demo scripts**
    - **Reasoning:** Demo scripts may have complex dependencies and state requirements. Using simple benchmarks establishes a clear baseline for the maximum scale possible, regardless of application-specific limitations.

## Current Limits & Observations

- **DinD Nodes:**
    - Maximum successful deployment: ~300 nodes and jobs
    - Beyond 300: Jobs time out during execution
    - Image pulling becomes problematic at scale
    - **Root causes:** Each DinD instance creates significant overhead by running separate Docker daemons. Network bandwidth becomes saturated with each node pulling images independently. Each daemon consumes memory and creates filesystem layers.

- **Host-Docker Nodes:**
    - More efficient than DinD (shared Docker daemon)
    - Hit cgroup limits around 600 nodes (1,200 containers total)
    - Error: `failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: unable to apply cgroup configuration`
    - **Root causes:** This specific error indicates that the cgroup controller cannot allocate resources for new containers. Even with a shared Docker daemon, the system still hits process, file descriptor, or memory tracking limits at this scale.

## Usage Commands

```bash
# Run with only host-Docker nodes (600)
docker compose up -d --scale nodes=0 --scale host-nodes=600

# Run with only DinD nodes (300)
docker compose up -d --scale nodes=300 --scale host-nodes=0

# Run benchmark jobs
bacalhau job run jobs/benchmark-light.yaml -V count=300

# Pre-pull images before running benchmarks
bacalhau job run jobs/benchmark-pull.yaml -V count=300
bacalhau job run jobs/benchmark-light.yaml -V count=300
```

## Recommendations for Further Scaling

1. **System Optimization:**
    - Review all settings in `optimize-for-containers.sh`
    - Reboot the system after applying
    - Critical settings include process limits, cgroup v2 configuration, and systemd limits
    - **Reasoning:** The script addresses the specific cgroup and resource limits encountered. A reboot ensures all kernel parameters and systemd settings are fully applied.

2. **Mixed Strategy:**
    - Use host-Docker nodes for maximum density (300-600)
    - Use DinD nodes when isolation is critical (up to 300)
    - **Reasoning:** Host-Docker nodes are more resource-efficient but share the Docker daemon state, which may cause conflicts in some scenarios. DinD provides better isolation but lower density. A mixed approach provides flexibility.

3. **Batch Processing:**
    - Instead of launching all nodes at once, consider scaling in batches
    - Pre-pull images before running actual workloads
    - **Reasoning:** Gradual scaling prevents overwhelming the system with simultaneous resource allocation. Spreading the load across time allows the system to stabilize between batches.

4. **Resource Allocation:**
    - Current setting: 0.04 CPU and 270MB RAM per node
    - Consider adjusting based on actual needs
    - **Reasoning:** The resource limits might be higher than actually needed. Profiling real usage could reveal opportunities to reduce allocations and increase density.

5. **Monitoring:**
    - Watch system resource usage during scaling tests
    - Key metrics: process count, memory usage, Docker socket activity
    - **Reasoning:** Monitoring helps identify the specific bottlenecks during scaling. This data guides further optimizations by focusing efforts on actual constraints.

## Known Issues

- **Image pulling can be a bottleneck with many DinD nodes**
    - **Reasoning:** Each DinD node pulls images independently, causing network contention and registry rate limiting. This creates a significant startup delay and can cause timeouts.
    - **Impact:** This becomes the primary scaling bottleneck for DinD nodes before system resource limits are reached.

- **cgroup limits may require further tuning for extreme scale**
    - **Reasoning:** Even with the optimizations in place, cgroup v2 controllers may still limit container creation at scale. The specific error message indicates that Docker is hitting systemd's cgroup integration limits.
    - **Impact:** This is the primary scaling bottleneck for host-Docker nodes, preventing deployment beyond ~600 nodes.

- **Demo scripts assume a fresh state, which may require restarting between runs**
    - **Reasoning:** Bacalhau's demo scripts often assume a clean environment with no leftover state from previous runs.
    - **Impact:** Running scaling tests before demos may leave the system in a non-clean state, requiring additional cleanup steps.

## Future Considerations

- **Explore having compute nodes use host network as well**
    - **Reasoning:** Host networking eliminates Docker's NAT overhead and may reduce memory usage per container. This could allow higher density at the cost of potential port conflicts.
    - **Trade-offs:** Better performance but less isolation between nodes.

- **Create a script to scale up in batches automatically**
    - **Reasoning:** Gradual scaling with stabilization periods between batches should allow higher maximum scale by preventing resource spikes.
    - **Implementation approach:** A script could monitor system metrics and add nodes in small increments only when the system has stabilized.

- **Consider a multi-host deployment for larger demos**
    - **Reasoning:** When a single host reaches its limits, distributing the load across multiple hosts is the next logical step.
    - **Implementation approach:** Docker Swarm or Kubernetes could be used to manage a cluster of hosts, with Bacalhau deployed across all of them.

- **Explore runtime resource limits rather than just deployment limits**
    - **Reasoning:** The system may support more containers if their actual resource usage is constrained at runtime.
    - **Implementation approach:** Fine-tune container resource limits and experiment with different Docker resource constraint settings.

## Technical Debt and Improvements

- **Error handling robustness**: Develop retry mechanisms for jobs when system is temporarily overloaded
- **Better Bacalhau node failure handling**: Improve how the system handles partial node failures at scale
- **Observability improvements**: Add centralized logging and monitoring for large deployments
- **Performance profiling**: Identify the specific operations that consume the most resources during scaling