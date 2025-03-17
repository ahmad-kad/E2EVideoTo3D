FROM python:3.7.9-slim as builder

# Install COLMAP build dependencies
RUN apt-get update && apt-get install -y \
    git \
    cmake \
    build-essential \
    libboost-program-options-dev \
    libboost-filesystem-dev \
    libboost-graph-dev \
    libboost-system-dev \
    libboost-test-dev \
    libeigen3-dev \
    libfreeimage-dev \
    libgoogle-glog-dev \
    libgflags-dev \
    libsqlite3-dev \
    libglew-dev \
    qtbase5-dev \
    libqt5opengl5-dev \
    libcgal-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add PPA for Ceres (on x86_64 only)
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        apt-get update && apt-get install -y software-properties-common && \
        apt-add-repository ppa:bzindovic/suitesparse-bugfix-1319687 -y && \
        apt-get update && apt-get install -y libsuitesparse-dev libceres-dev; \
    else \
        # On ARM64 we'll build Ceres from source
        apt-get update && apt-get install -y \
        libgoogle-glog-dev \
        libatlas-base-dev \
        libeigen3-dev \
        libsuitesparse-dev \
        && cd /tmp \
        && git clone https://github.com/ceres-solver/ceres-solver.git \
        && cd ceres-solver \
        && git checkout 1.14.0 \
        && mkdir build \
        && cd build \
        && cmake .. -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF \
        && make -j2 \
        && make install; \
    fi

# Build FLANN from source if needed
RUN if [ "$(uname -m)" = "x86_64" ]; then \
        apt-get update && apt-get install -y libflann-dev; \
    else \
        # On ARM64 we'll build FLANN from source
        cd /tmp \
        && git clone https://github.com/flann-lib/flann.git \
        && cd flann \
        && mkdir build \
        && cd build \
        && cmake .. -DBUILD_EXAMPLES=OFF -DBUILD_TESTS=OFF -DBUILD_DOC=OFF \
        && make -j2 \
        && make install; \
    fi

# Clone COLMAP
WORKDIR /opt
RUN git clone https://github.com/colmap/colmap.git
WORKDIR /opt/colmap
RUN git checkout 3.7
RUN mkdir build
WORKDIR /opt/colmap/build

# Build COLMAP with runtime detection of available resources
RUN ARCH=$(uname -m); \
    # Calculate build cores based on architecture
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then \
        BUILD_CORES=2; \
    else \
        TOTAL_CORES=$(nproc); \
        BUILD_CORES=$(( TOTAL_CORES / 2 > 2 ? TOTAL_CORES / 2 : 2 )); \
    fi; \
    echo "Building with $BUILD_CORES cores"; \
    \
    # Set up CUDA options
    CUDA_ENABLED=OFF; \
    if [ "$ARCH" = "x86_64" ] && [ -e /usr/local/cuda ]; then \
        echo "Building with CUDA support for x86_64"; \
        CUDA_ENABLED=ON; \
        CMAKE_OPTIONS="-DCMAKE_BUILD_TYPE=Release -DCUDA_ENABLED=ON -DCUDA_ARCHS=all"; \
    else \
        echo "Building without CUDA support"; \
        CMAKE_OPTIONS="-DCMAKE_BUILD_TYPE=Release -DCUDA_ENABLED=OFF"; \
    fi; \
    \
    # Build with memory optimizations
    export CXXFLAGS="-O2 -g0"; \
    cmake .. $CMAKE_OPTIONS && \
    make -j$BUILD_CORES && \
    make install

# Start with a clean image based on Python 3.7.9
FROM python:3.7.9-slim

# Install COLMAP runtime dependencies
RUN apt-get update && apt-get install -y \
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
    libqt5core5a \
    libqt5opengl5 \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy COLMAP binaries from the builder stage
COPY --from=builder /usr/local/bin/colmap /usr/local/bin/colmap

# Install reconstruction-specific Python packages
COPY requirements-reconstruction.txt /app/
RUN pip3 install --no-cache-dir -r requirements-reconstruction.txt

# Copy the reconstruction code and scripts
COPY src /app/src
COPY scripts /app/scripts
COPY reconstruct.py /app/

# Set environment variable for COLMAP
ENV COLMAP_PATH=/usr/local/bin/colmap
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONWARNINGS="ignore::DeprecationWarning"

# Set working directory
WORKDIR /app

# Default command runs the reconstruction script
CMD ["python3", "reconstruct.py", "--help"] 