# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the access logs into the container, and uncompress at /app/access_logs/
COPY access_logs.tar.bz2 /app/access_logs.tar.bz2
RUN mkdir -p /app/access_logs/ \
    && tar -xjf access_logs.tar.bz2 -C /app/access_logs/ \
    && rm access_logs.tar.bz2

# Copy the required files into the container at /app
COPY log-generator.py /app/log-generator.py

# Set the default executable
ENTRYPOINT ["python", "log-generator.py", "--input-log-directory", "/app/access_logs/"]