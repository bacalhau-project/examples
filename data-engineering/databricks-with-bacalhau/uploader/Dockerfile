FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the upload script
COPY upload_sqlite_to_s3.py ./

# Entry point
ENTRYPOINT ["python", "upload_sqlite_to_s3.py"]