# Use an official Python runtime as a parent image
FROM ubuntu:latest

# Set the working directory in the container
WORKDIR /app

# Copy the contents of the "/scripts" folder into the container at /app
COPY query.py .

RUN apt-get update && \
    apt-get install -y python3 python3-pip

RUN pip3 install psutil

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Run the script when the container launches
CMD ["python3", "query.py"]
