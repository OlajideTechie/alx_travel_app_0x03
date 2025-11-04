# ---------- Stage 1 : builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install build dependencies for mysqlclient
RUN apt-get clean && rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing && \
    apt-get install -y --no-install-recommends \
        gcc \
        pkg-config \
        default-libmysqlclient-dev \
        libmariadb3 \
        libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn celery flower

# ---------- Stage 2 : runtime ----------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/usr/local/bin:$PATH"

# Install runtime dependencies
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update --fix-missing && \
    echo "Acquire::Retries \"3\";" > /etc/apt/apt.conf.d/80-retries && \
    apt-get install -y --no-install-recommends libmariadb3 libmariadb-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy project code
COPY . .

# Expose port for Render web service
EXPOSE $PORT

# ---------- ENTRYPOINTS ----------
# For Render, you’ll specify the CMD per service:
# Web service: Run this in Render's web service CMD
# CMD ["gunicorn", "alx_travel_app.wsgi:application", "--bind", "0.0.0.0:$PORT", "--workers", "3"]

# Worker service: Run this in Render's worker service CMD
# CMD ["celery", "-A", "alx_travel_app", "worker", "-l", "info"]

# Optional Flower monitoring (if you want a separate service)
# CMD ["celery", "-A", "alx_travel_app", "flower", "--port=5555"]