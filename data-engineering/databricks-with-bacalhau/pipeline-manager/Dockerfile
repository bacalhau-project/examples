FROM python:3.11-slim

# Install uv for dependency management
RUN pip install uv

# Create app directory
WORKDIR /app

# Copy the pipeline controller script
COPY pipeline_controller.py .

# Make the script executable
RUN chmod +x pipeline_controller.py

# Create a volume mount point for the database
VOLUME ["/data"]

# Default command shows help
CMD ["python", "pipeline_controller.py", "--db", "/data/sensor_data.db", "--help"]