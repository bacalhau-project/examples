FROM uv:latest

# Set working directory
WORKDIR /app

# Copy the uploader script
COPY upload_sqlite_to_s3.py ./

# Pre-cache Python dependencies via UV-run
RUN uv run -s upload_sqlite_to_s3.py --help || true

# Use UV-run to execute the script
ENTRYPOINT ["uv", "run", "-s", "upload_sqlite_to_s3.py"]