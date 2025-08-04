# THE FIX: Use the full Python image, not the slim version, to include necessary system libraries.
FROM python:3.11

# Install system dependencies including ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    nginx \
    supervisor \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python requirements. Using --no-cache-dir is still a good practice.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the application code
COPY . .

# Copy nginx and supervisor configs
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]