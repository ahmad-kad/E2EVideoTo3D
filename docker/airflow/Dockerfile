FROM apache/airflow:2.6.3-python3.7

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1-mesa-glx \
    wget \
    git \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Switch to airflow user to install Python dependencies
USER airflow

# Set Python environment
ENV PYTHONWARNINGS="ignore::DeprecationWarning"

# Install our custom requirements
COPY --chown=airflow:root requirements-airflow.txt /opt/airflow/
RUN pip install --no-cache-dir -r /opt/airflow/requirements-airflow.txt

# Create directories
USER root
RUN mkdir -p /opt/airflow/data/input \
    /opt/airflow/data/output \
    /opt/airflow/data/videos \
    && chown -R airflow:root /opt/airflow/data

# Copy scripts
COPY --chown=airflow:root docker/scripts/airflow-entrypoint.sh /opt/airflow/
RUN chmod +x /opt/airflow/airflow-entrypoint.sh

USER airflow

# Set Python path
ENV PYTHONPATH=/opt/airflow:$PYTHONPATH

ENTRYPOINT ["/opt/airflow/airflow-entrypoint.sh"] 