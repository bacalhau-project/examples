FROM ubuntu:22.04
WORKDIR /backend

RUN apt-get update
RUN apt-get install python3 python3-pip curl unzip mc vim nano openssh-client -y
RUN pip install uv
RUN curl -sL https://get.bacalhau.org/install.sh | bash

RUN if [ "$(uname -m)" = "aarch64" ] || [ "$(uname -m)" = "arm64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
    else \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
    fi
RUN unzip awscliv2.zip
RUN ./aws/install

COPY . .

RUN ssh-keygen -t rsa -b 4096 -N "" -f /root/.ssh/id_rsa

CMD ["sleep", "infinity"]
