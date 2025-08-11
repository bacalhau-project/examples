FROM python:3.11-slim

# Install dependencies
RUN pip install --no-cache-dir \
    click \
    tabulate \
    python-dateutil

# Create app directory
WORKDIR /app

# Copy the pipeline controller script and dependencies
COPY pipeline_controller.py config_db.py ./

# Make the script executable
RUN chmod +x pipeline_controller.py

# Create a volume mount point for the database
VOLUME ["/data"]

# Set entrypoint to the Python script
ENTRYPOINT ["python", "pipeline_controller.py"]

# Default command shows help
CMD ["--help"]