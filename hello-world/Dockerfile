FROM cgr.dev/chainguard/python:latest-dev AS builder

ENV LANG=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/hello-world-builder/venv/bin:$PATH"

WORKDIR /hello-world-builder

RUN python -m venv /hello-world-builder/venv

RUN pip install --no-cache-dir psutil pyyaml

FROM cgr.dev/chainguard/python:latest

WORKDIR /hello-world-app

ENV PYTHONUNBUFFERED=1
ENV PATH="/venv/bin:$PATH"

COPY main.py hello-world-message.txt ./
COPY --from=builder /hello-world-builder/venv /venv

ENTRYPOINT [ "python", "/hello-world-app/main.py" ]