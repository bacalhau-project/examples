# Start with Ubuntu 20.04 as the base image
FROM ubuntu:20.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Set up environment variables
ENV HDF5_VERSION=1.14.3
ENV HDF5_DIR=/usr/local/hdf5
ENV PATH=$PATH:$HDF5_DIR/bin
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$HDF5_DIR/lib

# Install necessary dependencies and GCC-9
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    zlib1g-dev \
    gcc-9 \
    g++-9 \
    git \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Set GCC-9 as the default compiler
RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-9 60 --slave /usr/bin/g++ g++ /usr/bin/g++-9

# Download and install HDF5
RUN wget https://support.hdfgroup.org/ftp/HDF5/releases/hdf5-${HDF5_VERSION%.*}/hdf5-$HDF5_VERSION/src/hdf5-$HDF5_VERSION.tar.gz

RUN tar xzf hdf5-${HDF5_VERSION}.tar.gz && \
    cd hdf5-${HDF5_VERSION} && \
    ./configure \
    --prefix=$HDF5_DIR \
    CFLAGS="-march=x86-64 -mtune=generic -O2 -pipe" \
    --enable-build-mode=production \
    --enable-shared \
    --enable-hl \
    --disable-sharedlib-rpath && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf hdf5-${HDF5_VERSION} hdf5-${HDF5_VERSION}.tar.gz && \
    ldconfig

# Verify the installation
RUN $HDF5_DIR/bin/h5cc -showconfig

# Clone and build ZFP
RUN git clone https://github.com/LLNL/zfp.git && \
    cd zfp && \
    mkdir build && cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=$ZFP_DIR -DBUILD_SHARED_LIBS=ON && \
    make -j$(nproc) && \
    make install && \
    cd ../.. && \
    rm -rf zfp && \
    ldconfig

# Clone and build H5Z-ZFP
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
    make install && \
    cd .. && \
    rm -rf H5Z-ZFP && \
    ldconfig

# Install h5py
RUN HDF5_DIR=$HDF5_DIR pip3 install --no-binary=h5py h5py

# Verify installations
RUN $HDF5_DIR/bin/h5cc -showconfig && \
    ldconfig -p | grep hdf5 && \
    ls -l $HDF5_DIR/lib/plugin && \
    ldd $HDF5_DIR/lib/plugin/libh5zzfp.so && \
    ldd $HDF5_DIR/lib/plugin/libzfp.so && \
    python3 -c "import h5py; print(h5py.__version__, h5py.version.hdf5_version)"

WORKDIR /app

# Set up Python virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate && \
    pip3 install --upgrade pip wheel setuptools

# Install Python requirements
COPY requirements.txt .
RUN . /app/venv/bin/activate && \
    pip3 install -r requirements.txt

# Copy the run command script
COPY run_command.py /app/

# Copy the tarball containing the built plugins
COPY build_plugins/output/hdf5_plugins.tar.gz /tmp/

# Extract the plugins and set up the HDF5_PLUGIN_PATH
RUN mkdir -p /usr/local/hdf5/lib/plugin && \
    tar -xzvf /tmp/hdf5_plugins.tar.gz -C /usr/local/hdf5/lib/plugin && \
    rm /tmp/hdf5_plugins.tar.gz

# Set the HDF5_PLUGIN_PATH environment variable
ENV HDF5_PLUGIN_PATH=/usr/local/hdf5/lib/plugin

# Set up entrypoint
ENTRYPOINT ["/bin/bash", "-c"]
CMD [". /app/venv/bin/activate && python3 /app/run_command.py"]