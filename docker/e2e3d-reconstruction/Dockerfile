FROM python:3.7.9-slim

# Set build arguments for platform-specific optimizations
ARG TARGETPLATFORM
ARG BUILDPLATFORM
RUN echo "Building on $BUILDPLATFORM for $TARGETPLATFORM"

# Install system dependencies with minimal output
RUN apt-get update && apt-get install -y --no-install-recommends \
    libboost-program-options1.67.0 \
    libboost-filesystem1.67.0 \
    libboost-graph1.67.0 \
    libboost-system1.67.0 \
    libboost-test1.67.0 \
    libeigen3-dev \
    libfreeimage3 \
    libgoogle-glog0v5 \
    libgflags2.2 \
    libsqlite3-0 \
    libglew2.1 \
    git \
    wget \
    unzip \
    ca-certificates \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install COLMAP build dependencies and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libsqlite3-dev \
    libfreeimage-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libatlas-base-dev \
    libsuitesparse-dev \
    libpq-dev \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Build Ceres Solver (required for COLMAP)
WORKDIR /opt
RUN git clone --depth 1 --branch 1.14.0 https://github.com/ceres-solver/ceres-solver.git
WORKDIR /opt/ceres-solver
RUN mkdir build
WORKDIR /opt/ceres-solver/build
RUN cmake .. -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF
RUN make -j$(nproc)
RUN make install
RUN ldconfig

# Clone and build COLMAP
WORKDIR /opt
RUN git clone --depth 1 --branch 3.7 https://github.com/colmap/colmap.git
WORKDIR /opt/colmap
RUN mkdir build
WORKDIR /opt/colmap/build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release -DCUDA_ENABLED=OFF
RUN make -j$(nproc)
RUN make install

# Cleanup build dependencies to reduce image size
RUN apt-get update && \
    apt-get remove -y cmake build-essential && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /opt/ceres-solver /opt/colmap

# Set up the app directory
WORKDIR /app

# Upgrade pip and install core packages
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

# Install core dependencies (simplified approach)
# Core packages
RUN pip3 install --no-cache-dir numpy==1.19.5 pillow==8.3.2 opencv-python-headless==4.5.5.64 \
    matplotlib==3.3.4 scikit-learn==0.24.2 boto3==1.19.8 tqdm==4.64.1 requests==2.29.0 \
    sqlalchemy==1.4.54 psycopg2-binary==2.8.6

# 3D reconstruction specific packages
RUN pip3 install --no-cache-dir \
    open3d==0.15.1 \
    numpy-stl==2.17.1 \
    trimesh==3.14.1 \
    pyntcloud==0.1.6 \
    plotly==5.13.1 \
    seaborn==0.11.2

# Copy source code
COPY src /app/src
COPY scripts /app/scripts
COPY reconstruct.py /app/

# Set environment variables
ENV PYTHONPATH=/app
ENV COLMAP_PATH=/usr/local/bin/colmap
ENV PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Set the entrypoint
ENTRYPOINT ["python3", "reconstruct.py"]

# Default command
CMD ["--help"] 