# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies for psycopg2 and general builds
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install to a temporary directory
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --prefix=/install -r requirements.txt

# Stage 2: Final image
FROM python:3.12-slim

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy project files
COPY . .

# Create a non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Expose the port Gunicorn will use
EXPOSE 8080

# Environment variables for PostgreSQL
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=alx_travel_app.settings

# Run Gunicorn for Django
CMD ["gunicorn", "alx_travel_app.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2"]