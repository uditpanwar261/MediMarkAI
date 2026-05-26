# MediMark AI — Dockerfile
# Uses Python 3.11-slim — stable, compatible with all dependencies

FROM python:3.11-slim

WORKDIR /app

# System deps for OpenCV + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgl1-mesa-glx \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip first to avoid build issues
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads/originals uploads/processed ml_models

# Non-root user for security
RUN useradd -m -u 1000 medimark && chown -R medimark:medimark /app
USER medimark

ENV PORT=5000
EXPOSE 5000

CMD gunicorn -c gunicorn.conf.py app:app
