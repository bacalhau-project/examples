FROM nvcr.io/nvidia/nemo:24.12

WORKDIR /workspace

# Create config directory and copy configs
RUN mkdir -p /workspace/cfg
COPY llama3.1_24.11.1/llama3.1_*.yaml /workspace/cfg/

# Copy training script
COPY run_training.sh /workspace/
RUN chmod +x /workspace/run_training.sh

ENTRYPOINT ["/bin/bash"]