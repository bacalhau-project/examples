FROM ubuntu:22.04
WORKDIR /backend

RUN apt-get update
RUN apt-get install python3 python3-pip curl unzip mc vim nano openssh-client -y
RUN pip install uv
RUN curl -sL https://get.bacalhau.org/install.sh | bash

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
RUN unzip awscliv2.zip
RUN ./aws/install

ENV BACALHAU_API_HOST \
    BACALHAU_API_TLS_USETLS \
    BACALHAU_TOKEN

COPY . . 

RUN ssh-keygen -t rsa -b 4096 -N "" -f /root/.ssh/id_rsa


CMD ["sleep", "infinity"]
