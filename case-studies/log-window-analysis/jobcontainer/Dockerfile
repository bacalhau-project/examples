FROM python:3.11.6-bullseye as builder

COPY ./requirements.txt /tmp/requirements.txt

# RUN pip3 install --index-url=https://www.piwheels.org/simple --no-cache-dir -r /tmp/requirements.txt

RUN pip3 install --no-cache-dir -r /tmp/requirements.txt --user

FROM python:3.11-slim-bullseye

COPY --from=builder /root/.local/lib/python3.11/site-packages /root/.local/lib/python3.11/site-packages

RUN ln -s $(which python3) /usr/bin/python
ENV PATH="/root/.local/lib/python3.11/site-packages:${PATH}"

WORKDIR /

RUN apt-get update && apt-get install -y curl gnupg

# Install Google Cloud SDK and gsutil
RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key --keyring /usr/share/keyrings/cloud.google.gpg add -
RUN apt-get update && apt-get install -y google-cloud-sdk

RUN rm -rf /var/lib/apt/lists/*

COPY ./process.py /process.py

ENTRYPOINT ["python3", "/process.py"]
