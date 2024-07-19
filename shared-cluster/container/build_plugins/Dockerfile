# Use a base image with necessary build tools
FROM ubuntu:20.04

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary build tools and compilers
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    gcc \
    g++ \
    gfortran \
    make \
    libssl-dev \
    zlib1g-dev \
    wget\ 
    && rm -rf /var/lib/apt/lists/*

# Set up environment variables
ENV ZFP_HOME=/usr/local
ENV HDF5_HOME=/usr
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib

# Install ZFP
RUN git clone https://github.com/LLNL/zfp.git && \
    cd zfp && \
    mkdir build && \
    cd build && \
    cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DBUILD_SHARED_LIBS=ON -DBUILD_UTILITIES=OFF -DBUILD_TESTING=OFF -DZFP_WITH_ALIGNED_ALLOC=OFF -DBIT_STREAM_WORD_TYPE=uint8 && \
    make && \
    make install && \
    ldconfig

# Install H5Z-ZFP
RUN git clone https://github.com/LLNL/H5Z-ZFP.git && \
    cd H5Z-ZFP && \
    make CC=gcc \
    ZFP_HOME=${ZFP_HOME} \
    HDF5_HOME=${HDF5_HOME} \
    DYLIB_SUFFIX=so \
    PREFIX=/usr/local \
    CFLAGS="-fPIC -I/usr/include/hdf5/serial" \
    LDFLAGS="-L/usr/lib/x86_64-linux-gnu/hdf5/serial" \
    all && \
    make install && \
    ldconfig

# Create a directory for the plugins
RUN mkdir -p /usr/local/hdf5/lib/plugin

# Copy the built plugins
# Copy the files and create symlinks
RUN cp /usr/local/lib/libzfp.so.1.0.1 /usr/local/hdf5/lib/plugin/ && \
    ln -s /usr/local/hdf5/lib/plugin/libzfp.so.1.0.1 /usr/local/hdf5/lib/plugin/libzfp.so.1 && \
    ln -s /usr/local/hdf5/lib/plugin/libzfp.so.1 /usr/local/hdf5/lib/plugin/libzfp.so

RUN cp /H5Z-ZFP/install/plugin/libh5zzfp.so /usr/local/hdf5/lib/plugin/

# Set the HDF5_PLUGIN_PATH environment variable
ENV HDF5_PLUGIN_PATH=/usr/local/hdf5/lib/plugin

# Create a tarball of the plugins
RUN tar -czvf /hdf5_plugins.tar.gz -C /usr/local/hdf5/lib/plugin .

# Output directory
VOLUME /output

# Copy the tarball to the output directory
CMD cp /hdf5_plugins.tar.gz /output/ && \
    echo $(date +%Y%m%d_%H%M%S) > /output/build_version.txt