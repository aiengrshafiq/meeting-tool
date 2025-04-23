# Use Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install OS-level dependencies
RUN apt-get update && apt-get install -y \
    build-essential curl git && \
    rm -rf /var/lib/apt/lists/*

# Copy dependencies
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy entire project
COPY . .

# Make sure entrypoint is executable
RUN chmod +x docker/entrypoint.sh

# Run via entrypoint
CMD ["bash", "docker/entrypoint.sh"]
