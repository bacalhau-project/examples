FROM python:3.12-slim-bullseye

ENV CRYPTOGRAPHY_DONT_BUILD_RUST=1
ENV HDF5_DIR=/usr

RUN apt-get update && apt-get install -y \
    gcc \
    libc-dev \
    linux-headers-generic \
    libhdf5-dev \
    libhdf5-serial-dev \
    libopenblas-dev \
    liblapack-dev \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libjpeg-dev \
    libmariadb-dev \
    libffi-dev \
    gfortran

WORKDIR /app

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate
RUN pip3 install --upgrade pip

COPY requirements.txt .
RUN pip3 install -r requirements.txt
RUN pip3 install --no-binary=h5py h5py

COPY run_command.py /app/

ENTRYPOINT ["python3", "/app/run_command.py"]