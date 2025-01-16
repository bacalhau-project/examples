#!/usr/bin/env bash

# Exit on error, undefined variables, and ensure pipe errors are caught
set -euo pipefail

###############################################
# Environment Configuration
###############################################

# Model configuration
: "${MODEL_SIZE:=8b}"       # Model size options: 8b, 70b, 405b
: "${DTYPE:=bf16}"          # Data type options: fp8, bf16
: "${NUM_GPUS:=8}"          # Number of GPUs for training

# Training hyperparameters
: "${GLOBAL_BATCH_SIZE:=128}"  # Total batch size across all GPUs
: "${SEQ_LEN:=8192}"          # Sequence length for training
: "${MAX_STEPS:=10}"          # Number of training steps (reduced for POC)

# Data configuration
: "${USE_SYNTHETIC_DATA:=true}"  # Set to false to use real dataset
: "${DATA_DIR:=/inputs}"         # Directory containing the real dataset if used
: "${RESULT_DIR:=/outputs}"      # Directory for outputs (logs, checkpoints)

# Create output directory
mkdir -p "${RESULT_DIR}"

###############################################
# Environment Settings for NeMo
###############################################

# These settings optimize NeMo's performance and behavior
export PYTHONUNBUFFERED=1           # Ensure Python output is unbuffered
export TOKENIZERS_PARALLELISM=False  # Avoid tokenizer warnings
export TRANSFORMERS_OFFLINE=1        # Don't try to download models
export TORCH_NCCL_AVOID_RECORD_STREAMS=1  # NCCL optimization
export CUDA_DEVICE_MAX_CONNECTIONS=1      # GPU connection optimization

###############################################
# Build Configuration Overrides
###############################################

# Start with empty config overrides
CONFIG_OVERRIDES=""

# Basic training configuration
CONFIG_OVERRIDES+=" trainer.num_nodes=1"                        # Single node training
CONFIG_OVERRIDES+=" trainer.devices=${NUM_GPUS}"               # Number of GPUs to use
CONFIG_OVERRIDES+=" trainer.max_steps=${MAX_STEPS}"            # Training duration
CONFIG_OVERRIDES+=" model.global_batch_size=${GLOBAL_BATCH_SIZE}"  # Global batch size
CONFIG_OVERRIDES+=" model.data.seq_length=${SEQ_LEN}"         # Sequence length
CONFIG_OVERRIDES+=" run.results_dir=${RESULT_DIR}"            # Output directory

# Data configuration based on synthetic vs real data
if [[ "${USE_SYNTHETIC_DATA}" == "true" ]]; then
    echo "Using synthetic data for training"
    CONFIG_OVERRIDES+=" model.data.data_impl=mock"     # Enable synthetic data
    CONFIG_OVERRIDES+=" model.data.data_prefix=\"\""   # Empty prefix for synthetic
else
    echo "Using real data for training from ${DATA_DIR}"
    CONFIG_OVERRIDES+=" model.data.data_impl=mmap"     # Memory-mapped real data
    # Configure data prefix with two splits (standard configuration)
    CONFIG_OVERRIDES+=" model.data.data_prefix=[\"0.5\",\"${DATA_DIR}/my-llama_00_text_document\",\"0.5\",\"${DATA_DIR}/my-llama_01_text_document\"]"
fi

###############################################
# Select Configuration File
###############################################

CONFIG_NAME="llama3.1_${MODEL_SIZE}.yaml"

###############################################
# Verify Environment and Start Training
###############################################

# Print training configuration
echo "Starting Llama 3.1 training with configuration:"
echo "- Model size: ${MODEL_SIZE}"
echo "- Data type: ${DTYPE}"
echo "- Number of GPUs: ${NUM_GPUS}"
echo "- Global batch size: ${GLOBAL_BATCH_SIZE}"
echo "- Sequence length: ${SEQ_LEN}"
echo "- Training steps: ${MAX_STEPS}"
echo "- Using synthetic data: ${USE_SYNTHETIC_DATA}"

# Verify critical paths and files
echo -e "\nVerifying critical paths..."
if [ ! -f "/workspace/cfg/${CONFIG_NAME}" ]; then
    echo "ERROR: Config file not found: /workspace/cfg/${CONFIG_NAME}"
    exit 1
fi

if [ ! -f "/opt/NeMo/examples/nlp/language_modeling/megatron_gpt_pretraining.py" ]; then
    echo "ERROR: NeMo training script not found"
    exit 1
fi

# Check for dataset only if using real data
if [[ "${USE_SYNTHETIC_DATA}" == "false" ]]; then
    if ! ls "${DATA_DIR}"/my-llama_00_text_document* >/dev/null 2>&1; then
        echo "WARNING: Dataset files not found in ${DATA_DIR}"
        echo "Please ensure dataset is properly mounted when using real data"
    fi
fi

# Start training
echo -e "\nLaunching training..."
python3 /opt/NeMo/examples/nlp/language_modeling/megatron_gpt_pretraining.py \
    --config-path=/workspace/cfg \
    --config-name="${CONFIG_NAME}" \
    ${CONFIG_OVERRIDES}

echo -e "\nTraining completed successfully!"