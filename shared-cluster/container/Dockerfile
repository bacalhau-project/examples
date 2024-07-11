FROM alpine:latest

# Install python3 and pip
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate
RUN pip3 install --upgrade pip

COPY container_requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY run_command.py /app/

ENTRYPOINT ["python3", "/app/run_command.py"]