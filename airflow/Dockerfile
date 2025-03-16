FROM apache/airflow:2.6.3-python3.10

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopencv-dev \
    cmake \
    git \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libeigen3-dev \
    libsuitesparse-dev \
    libfreeimage-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    libceres-dev \
    nvidia-cuda-toolkit \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install COLMAP
WORKDIR /tmp
RUN git clone https://github.com/colmap/colmap.git && \
    cd colmap && \
    git checkout 3.8 && \
    mkdir build && \
    cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DCUDA_ENABLED=ON && \
    make -j$(nproc) && \
    make install && \
    cd /tmp && \
    rm -rf colmap

# Set back to airflow user
USER airflow

# Install Python dependencies
COPY requirements.txt /opt/airflow/requirements.txt
RUN pip install --no-cache-dir -r /opt/airflow/requirements.txt

# Create required directories
RUN mkdir -p /opt/airflow/data/input \
    /opt/airflow/data/output \
    /opt/airflow/data/videos

# Set working directory
WORKDIR /opt/airflow 