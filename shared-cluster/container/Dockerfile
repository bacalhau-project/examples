FROM python:3.12-slim-bullseye

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1

# Install necessary dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libc-dev \
    libhdf5-dev \
    libopenblas-dev \
    liblapack-dev \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libjpeg-dev \
    libmariadb-dev \
    libffi-dev \
    gfortran \
    cmake \
    git \
    hdf5-tools \
    libhdf5-dev \
    libhdf5-serial-dev \
    m4 \
    bison \
    flex \
    libtool \
    autoconf \
    automake \
    pkg-config \
    gettext \
    libncurses5-dev \
    libncursesw5-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-openssl-dev \
    libexpat1-dev \
    libiconv-hook-dev \
    libiconv-hook1

# Install Spack
RUN git clone https://github.com/llnl/spack.git /opt/spack && \
    cd /opt/spack && \
    git checkout releases/v0.20

# Set up Spack environment
ENV SPACK_ROOT=/opt/spack
ENV PATH="${SPACK_ROOT}/bin:${PATH}"
SHELL ["/bin/bash", "-c"]

# Install H5Z-ZFP using Spack
RUN . /opt/spack/share/spack/setup-env.sh && \
    spack install h5z-zfp || { echo "Spack install failed"; exit 1; }

# Set HDF5_PLUGIN_PATH
RUN echo '. /opt/spack/share/spack/setup-env.sh' >> /etc/bash.bashrc && \
    echo 'export HDF5_PLUGIN_PATH=$(spack location -i h5z-zfp)/lib' >> /etc/bash.bashrc

WORKDIR /app

# Set up Python virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate && \
    pip3 install --upgrade pip

# Install Python requirements
COPY requirements.txt .
RUN . /app/venv/bin/activate && \
    pip3 install -r requirements.txt

# Copy the run command script
COPY run_command.py /app/

# Set up entrypoint to ensure Spack environment is loaded
ENTRYPOINT ["/bin/bash", "-c"]
CMD [". /opt/spack/share/spack/setup-env.sh && . /app/venv/bin/activate && python3 /app/run_command.py"]