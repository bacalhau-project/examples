# Llama 3.1 8B Training Example for Bacalhau

This repository contains a single-node training example using NVIDIA's Llama 3.1 8B model, adapted for running on Bacalhau. This is a simplified version that demonstrates basic LLM training capabilities using 8 GPUs on a single node.

Based on https://catalog.ngc.nvidia.com/orgs/nvidia/teams/dgxc-benchmarking/resources/llama31-8b-dgxc-benchmarking-a

## Overview

- Single-node training of Llama 3.1 8B model
- Uses NVIDIA's NeMo framework
- Supports 8 GPUs on a single node
- Uses synthetic data by default
- Supports both FP8 and BF16 data types


## Structure

```
.
├── Dockerfile                  # Container definition using NeMo base image
├── llama3.1_24.11.1/          # Configuration files
│   └── llama3.1_8b.yaml       # 8B model configuration
├── run_training.sh            # Main training script
└── sample-jobs.yaml           # Bacalhau job definition
```

## Building and Pushing the Image

1. Login to GitHub Container Registry:
```bash
echo $GITHUB_PAT | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

2. Build and push the image:
```bash
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/bacalhau-project/llama3-benchmark:24.12 \
  -t ghcr.io/bacalhau-project/llama3-benchmark:latest \
  --push .
```

## Running on Bacalhau

Basic training job (10 steps with synthetic data):
```bash
bacalhau job run sample-job.yaml -V "steps=10"
```

Environment variables for customization:
- `DTYPE`: Data type (fp8, bf16)
- `MAX_STEPS`: Number of training steps
- `USE_SYNTHETIC_DATA`: Whether to use synthetic data (default: true)


## Output

Training results and logs are saved to the `/results` directory which gets:
1. Published to S3
2. Available in the job outputs

The results include:
- Training logs
- Performance metrics
- TensorBoard logs

## Resources Required

Fixed requirements:
- 8x NVIDIA H100 GPUs (80GB each)
- 32 CPU cores
- 640GB system memory

## Notes

- Uses synthetic data by default - no data preparation needed
- Training script is optimized for H100 GPUs
- All settings are tuned for single-node performance
