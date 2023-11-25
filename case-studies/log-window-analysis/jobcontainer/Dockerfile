FROM cgr.dev/chainguard/python:latest-dev as builder

WORKDIR /app

COPY requirements.txt .

COPY ./requirements.txt /tmp/requirements.txt

# RUN pip3 install --index-url=https://www.piwheels.org/simple --no-cache-dir -r /tmp/requirements.txt

RUN pip3 install --no-cache-dir -r /tmp/requirements.txt --user

# Install Google Cloud SDK and gsutil
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
RUN apt-get update && apt-get install -y google-cloud-sdk

RUN rm -rf /var/lib/apt/lists/*

FROM cgr.dev/chainguard/python:latest

WORKDIR /

# Make sure you update Python version in path
COPY --from=builder /home/nonroot/.local/lib/python3.11/site-packages /home/nonroot/.local/lib/python3.11/site-packages

COPY ./process.py /process.py

ENTRYPOINT ["python3", "/process.py"]
