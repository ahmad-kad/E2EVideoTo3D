FROM nvidia/cuda:12.1-base-ubuntu22.04

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Meshroom (this is a simplified version, actual installation may vary)
RUN wget https://github.com/alicevision/meshroom/releases/download/v2023.1.0/Meshroom-2023.1.0-linux-cuda12.1.tar.gz \
    && tar -xzf Meshroom-2023.1.0-linux-cuda12.1.tar.gz \
    && rm Meshroom-2023.1.0-linux-cuda12.1.tar.gz \
    && ln -s /app/Meshroom-2023.1.0/meshroom_batch /usr/local/bin/meshroom_batch

# Copy project code
COPY . .

# Set the entrypoint
ENTRYPOINT ["python3", "-m"] 