FROM python:3.11-slim

WORKDIR /app

# System dependencies for OpenCV + MySQL
RUN apt-get update && apt-get install -y \
    libglib2.0-0 libsm6 libxext6 libxrender-dev \
    libgomp1 libgl1-mesa-glx \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Create upload directories
RUN mkdir -p uploads/originals uploads/processed ml_models

# Non-root user for security
RUN useradd -m -u 1000 medimark && chown -R medimark:medimark /app
USER medimark

EXPOSE 5000

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "--timeout", "120", "app:app"]
