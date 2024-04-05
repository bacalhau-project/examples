FROM alpine:3.19.1

# Install python3 and pip
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"
RUN . /app/venv/bin/activate
RUN pip3 install --upgrade pip

COPY requirements.txt .
RUN pip3 install -r requirements.txt

COPY edit_color.py .

ENTRYPOINT ["python3", "edit_color.py"]

