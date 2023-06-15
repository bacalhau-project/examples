FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-devel

# update NVIDIA repo key
# https://developer.nvidia.com/blog/updating-the-cuda-linux-gpg-repository-key/
ARG distro=ubuntu2004
ARG arch=x86_64
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/$distro/$arch/3bf863cc.pub

ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update && \
    apt-get -y install \
          libglib2.0-0 \
          libsm6 \
          libxrender-dev \
          libxext6 \
          python3-setuptools \
          git \
          wget \
          python3-opencv \
          pkg-config \
          build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /

RUN pip install --upgrade pip

RUN pip install torch torchvision

RUN pip install -U git+https://github.com/luca-medeiros/lang-segment-anything.git

RUN wget https://gist.githubusercontent.com/js-ts/5e793550565ef1b70c1730792c5db505/raw/f6bb7bd4bd22c49ae438dc44dd58fe678890ac2a/sam-test.py

RUN wget https://gist.githubusercontent.com/js-ts/23f4a0a1ae18d2ef0717022f4663a599/raw/b38ad83c7f6dc5197d002f44d008b54a48a1bcd2/sam.py

RUN wget https://raw.githubusercontent.com/luca-medeiros/lang-segment-anything/main/assets/car.jpeg

RUN python sam-test.py