FROM davidgasquez/duckdb:latest

RUN apt-get update && apt-get install -y python3 python3-pip curl wget lsb-release gnupg

# Install Google Cloud SDK and gsutil
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add - && \
    apt-get update -y && apt-get install google-cloud-sdk -y

RUN pip3 install duckdb requests google-cloud-storage pandas

RUN apt-get update -y && apt-get install curl wget -y

WORKDIR /
# You can copy the script instead of downlaoding it
# COPY ./process.py /process.py
RUN wget https://gist.githubusercontent.com/js-ts/cd0f5816aacbc50b2dc692e1c7f4bc90/raw/07e0ceffe72031b5dfb76a53df4a81e533b495b3/process.py