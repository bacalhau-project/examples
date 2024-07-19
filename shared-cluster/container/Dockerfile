FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools and dependencies
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    build-essential \
    zlib1g-dev \
    libopenmpi-dev \
    hdf5-tools \
    libhdf5-dev \
    cmake \
    git \
    curl \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3.11-venv \
    && rm -rf /var/lib/apt/lists/*

SHELL [ "/bin/bash", "-c" ]

# Update alternatives
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Set working directory
WORKDIR /app

# Install conda
RUN curl -LsSf https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh
RUN bash miniconda.sh -b -p /opt/conda
ENV PATH="/opt/conda/bin:$PATH"

# Install
RUN conda install --yes -c conda-forge mamba

# Create a new conda environment
RUN mamba create -n h5pyenv

# Install everything from requirements.txt
COPY requirements.txt .
RUN bash -c "mamba install -n h5pyenv -c conda-forge --file requirements.txt"

# Copy your Python script and entrypoint script (adjust as needed)
COPY run_command.py .

# Set up entrypoint (adjust based on your actual script)
ENTRYPOINT ["/bin/bash", "-c"]

# Run the script in the conda environment
CMD ["mamba", "run", "-n", "h5pyenv", "python", "run_command.py"]
