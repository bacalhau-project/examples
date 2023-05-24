FROM debian:bullseye

RUN apt-get clean -y && apt-get update -y

RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -

RUN apt-get update && apt-get install -y \
    wget unzip \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://github.com/duckdb/duckdb/releases/download/v0.7.1/duckdb_cli-linux-amd64.zip \
    && unzip duckdb_cli-linux-amd64.zip -d /usr/local/bin \
    && rm duckdb_cli-linux-amd64.zip

RUN apt-get update && apt-get install -y python3 python3-pip curl wget lsb-release gnupg

# Install Google Cloud SDK and gsutil
RUN apt-get install google-cloud-sdk -y

RUN pip3 install duckdb requests google-cloud-storage pandas

WORKDIR /

COPY ./process.py /process.py