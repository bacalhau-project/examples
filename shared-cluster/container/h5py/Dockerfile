FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

SHELL [ "/bin/bash", "-c" ]

# Set working directory
WORKDIR /app

# Install conda
RUN curl -LsSf https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh
RUN bash miniconda.sh -b -p /opt/conda
ENV PATH="/opt/conda/bin:$PATH"

# Install mamba
RUN conda install --yes -c conda-forge mamba

# Copy your environment file
COPY h5pyenv.yaml .

# Create the environment from the YAML file
RUN mamba env create -f h5pyenv.yaml

# Activate the environment in the entrypoint
ENTRYPOINT ["/bin/bash", "-c"]

# Copy the run_command.py file
COPY run_command.py .

# Set the default command to activate the environment
CMD ["source activate h5pyenv && python run_command.py"]