FROM ghcr.io/bacalhau-project/duckdb:latest

# Install curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Add /root/.local/bin to PATH
ENV PATH="/root/.local/bin:$PATH"

# Create and activate virtual environment
RUN uv venv /root/.venv --seed --python 3.12
ENV VIRTUAL_ENV=/root/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install packages in the virtual environment
RUN uv pip install --upgrade pip

# Copy the initial log process script in so we can run and pre-cache the dependencies
COPY log_process_0.py /log_process_0.py
RUN uv run -s /log_process_0.py --exit

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
