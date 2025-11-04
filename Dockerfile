# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies for Postgres + Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Final image
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy project files
COPY . .

# Create a non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Expose port
EXPOSE 8080

# Start Gunicorn and Celery using supervisord
CMD ["supervisord", "-c", "/app/supervisord.conf"]