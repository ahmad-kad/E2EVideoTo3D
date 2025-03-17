FROM python:3.7.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONWARNINGS="ignore::DeprecationWarning"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    wget \
    git \
    curl \
    build-essential \
    libboost-all-dev \
    pkg-config \
    libpq-dev \
    cmake \
    libssl-dev \
    libre2-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Install dependencies in a more organized way
# First, common packages with defined versions
COPY requirements-common.txt /app/
RUN pip3 install --no-cache-dir -r requirements-common.txt

# Install GPU packages conditionally at runtime
COPY docker/scripts/detect_gpu.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/detect_gpu.sh

# Create standard directories
RUN mkdir -p /app/data/input \
    /app/data/output \
    /app/data/videos \
    /app/logs

# Set entrypoint for environment detection and setup
COPY docker/scripts/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["python3", "-m", "src.main"] 