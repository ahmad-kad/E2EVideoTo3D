FROM ubuntu:22.04

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV MESHROOM_VERSION 2021.1.0


# Install system dependencies
RUN apt-get update && apt-get install -y wget

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    gcc \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    wget \
    git \
    python3-opencv \
    build-essential \
    libboost-all-dev \
    pkg-config \
    libpq-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Set working directory
WORKDIR /app

# Install dependencies in groups to isolate issues
COPY requirements.txt .

# Core and data handling packages first
RUN pip3 install --no-cache-dir \
    opencv-python>=4.7.0 \
    numpy>=1.22.0 \
    pillow>=9.4.0 \
    boto3>=1.26.0 \
    s3fs>=2023.3.0 \
    pandas>=1.5.0 \
    pyarrow>=12.0.0

# Database packages
RUN pip3 install --no-cache-dir \
    psycopg2-binary>=2.9.6 \
    sqlalchemy>=1.4.36,\<2.0.0

# Spark and processing
RUN pip3 install --no-cache-dir \
    pyspark>=3.4.0 \
    findspark>=2.0.1

# Install the rest with relaxed constraints
RUN pip3 install --no-cache-dir --use-pep517 -r requirements.txt || echo "Some packages failed to install"

# Install additional GPU packages conditionally at runtime
COPY setup_environment.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/setup_environment.sh

# Download and install Meshroom
RUN mkdir -p /opt/meshroom && \
    cd /opt/meshroom && \
    wget -q "https://github.com/alicevision/meshroom/releases/download/v${MESHROOM_VERSION}/Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz" && \
    tar -xzf Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz && \
    rm Meshroom-${MESHROOM_VERSION}-linux-cuda10.tar.gz && \
    ln -s /opt/meshroom/Meshroom-${MESHROOM_VERSION}-cuda10/meshroom_batch /usr/local/bin/meshroom_batch_cpu

    # Copy project code
COPY . .

# Entry point will check environment and set up accordingly
ENTRYPOINT ["/usr/local/bin/setup_environment.sh"]
CMD ["python3", "-m"]