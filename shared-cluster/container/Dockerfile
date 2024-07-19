FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Install essential tools, dependencies, and HDF5 prerequisites
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    zlib1g-dev \
    python3 \  
    python3-dev \ 
    python3-pip \
    libopenmpi-dev \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Download and extract HDF5
ENV HDF5_VERSION=1.14.3
ENV HDF5_DIR=/usr/local/hdf5
ENV PATH=$PATH:$HDF5_DIR/bin
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HDF5_DIR/lib

RUN wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-${HDF5_VERSION%.*}/hdf5-$HDF5_VERSION/src/hdf5-$HDF5_VERSION.tar.gz && \
    tar -xzf hdf5-${HDF5_VERSION}.tar.gz 

# Configure and build HDF5 (with optimization disabled)
WORKDIR /hdf5-${HDF5_VERSION}
RUN ./configure --prefix=$HDF5_DIR --enable-shared --enable-build-mode=production CFLAGS="-march=x86-64" && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Clone, build, and install ZFP
ENV ZFP_DIR=/usr/local/zfp
RUN git clone https://github.com/LLNL/zfp.git && \
    cd zfp && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=$ZFP_DIR -DBUILD_SHARED_LIBS=ON && \
    make -j$(nproc) && \
    make install && \
    cd ../.. && \
    rm -rf zfp

# Clone, build, and install H5Z-ZFP (HDF5 ZFP Filter)
RUN git clone https://github.com/LLNL/H5Z-ZFP.git && \
    cd H5Z-ZFP && \
    make CC=gcc \
    ZFP_HOME=$ZFP_DIR \
    HDF5_HOME=$HDF5_DIR \
    DYLIB_SUFFIX=so \
    PREFIX=$HDF5_DIR \
    H5Z_ZFP_USE_PLUGIN_INIT=yes \
    CFLAGS="-fPIC -I$ZFP_DIR/include -I$HDF5_DIR/include" \
    LDFLAGS="-L$ZFP_DIR/lib -L$HDF5_DIR/lib" \
    all && \
    make install

# Verify HDF5 and plugins are correctly installed
RUN $HDF5_DIR/bin/h5cc -showconfig && \
    ldconfig -p | grep hdf5 && \
    ls -l $HDF5_DIR/lib/plugin

# Set the HDF5_PLUGIN_PATH environment variable
ENV HDF5_PLUGIN_PATH=$HDF5_DIR/lib/plugin

# Install h5py (with parallel HDF5 support) after the plugins
RUN pip3 install --no-cache-dir "h5py==3.9.0"

# Set working directory
WORKDIR /app

# Copy requirements and install (optional if you have other dependencies)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy your Python script and entrypoint script (adjust as needed)
COPY run_command.py .

# Set up entrypoint (adjust based on your actual script)
ENTRYPOINT ["/bin/bash", "-c"]
CMD [". /app/venv/bin/activate && python3 run_command.py"]
