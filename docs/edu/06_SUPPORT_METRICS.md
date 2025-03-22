# Monitoring and Metrics System

## Introduction

The monitoring and metrics system in E2E3D provides comprehensive visibility into the platform's performance, health, and operational status. This document explains the monitoring architecture, metrics collection, visualization, and how to use this data for troubleshooting and optimization.

## Monitoring Concepts

### Types of Metrics

The E2E3D monitoring system captures several types of data:

**System Metrics**:
- CPU, memory, disk, and network usage
- Container health and resource utilization
- Database performance

**Application Metrics**:
- Job processing times and success rates
- API response times and request rates
- Component-specific performance metrics

**Business Metrics**:
- Total jobs processed
- Average reconstruction time
- Success/failure rates by dataset type

### Observability Pillars

Complete observability in E2E3D is built on three pillars:

1. **Metrics**: Numerical data points collected over time
2. **Logs**: Detailed text records of application events
3. **Traces**: End-to-end tracking of requests through the system

## Monitoring Architecture

### Components

The E2E3D monitoring stack consists of:

1. **Prometheus**: Time-series database for metric storage and querying
   - Collects and stores metrics from all components
   - Supports powerful query language (PromQL)
   - Handles alerting based on metric thresholds

2. **Grafana**: Visualization and dashboarding
   - Provides customizable dashboards for different stakeholders
   - Connects to Prometheus for data source
   - Supports alerting and annotations

3. **Node Exporter**: System-level metrics collection
   - Exposes host-level metrics (CPU, memory, disk, network)
   - Runs as a sidecar in containerized environments

4. **cAdvisor**: Container metrics collection
   - Provides container resource usage and performance statistics
   - Integrates with Docker and Kubernetes

5. **Application Instrumentation**: Custom metrics from E2E3D services
   - API service metrics
   - Reconstruction service metrics
   - Database metrics

### Metric Collection Flow

The flow of metrics through the system:

1. Components expose metrics endpoints (usually `/metrics`)
2. Prometheus scrapes these endpoints at regular intervals
3. Metrics are stored in Prometheus time-series database
4. Grafana queries Prometheus and displays the data
5. Alerting rules trigger notifications when thresholds are exceeded

## Implementation Details

### Prometheus Configuration

Prometheus is configured through a YAML file:

```yaml
# prometheus.yml (excerpt)
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'api'
    static_configs:
      - targets: ['api:5000']

  - job_name: 'reconstruction'
    static_configs:
      - targets: ['reconstruction:5001']

  - job_name: 'minio'
    metrics_path: /minio/v2/metrics/cluster
    static_configs:
      - targets: ['minio:9000']

rule_files:
  - 'alert_rules.yml'
```

### Metric Instrumentation

Python services in E2E3D use Prometheus client libraries for instrumentation:

```python
# Example API service instrumentation
from prometheus_client import Counter, Histogram, start_http_server
import time

# Define metrics
API_REQUESTS = Counter('api_requests_total', 'Total count of API requests', ['method', 'endpoint', 'status'])
API_LATENCY = Histogram('api_request_duration_seconds', 'API request latency', ['method', 'endpoint'])
JOBS_CREATED = Counter('jobs_created_total', 'Total count of jobs created')
JOBS_COMPLETED = Counter('jobs_completed_total', 'Total count of completed jobs')
JOBS_FAILED = Counter('jobs_failed_total', 'Total count of failed jobs')

# Instrument a Flask route
@app.route('/api/job', methods=['POST'])
def create_job():
    start_time = time.time()
    try:
        # Process request
        # ...
        JOBS_CREATED.inc()
        API_REQUESTS.labels(method='POST', endpoint='/api/job', status='success').inc()
        return jsonify({"status": "success", "job_id": job_id})
    except Exception as e:
        API_REQUESTS.labels(method='POST', endpoint='/api/job', status='error').inc()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        API_LATENCY.labels(method='POST', endpoint='/api/job').observe(time.time() - start_time)
```

### Grafana Dashboards

Grafana dashboards are organized into several categories:

1. **System Overview**: Overall health and resource usage
2. **API Performance**: Request rates, latencies, and error rates
3. **Reconstruction Performance**: Processing times and resource usage
4. **Storage Metrics**: Disk usage and object counts
5. **Job Statistics**: Success rates and processing times by job type

## Key Metrics

### System Health Metrics

Critical metrics for system health:

- **Node CPU Usage**: `node_cpu_seconds_total`
- **Node Memory Usage**: `node_memory_MemTotal_bytes - node_memory_MemFree_bytes`
- **Disk Space**: `node_filesystem_avail_bytes / node_filesystem_size_bytes`
- **Network I/O**: `node_network_receive_bytes_total`, `node_network_transmit_bytes_total`

### Application Performance Metrics

Metrics specific to E2E3D application performance:

- **API Request Rate**: `rate(api_requests_total[5m])`
- **API Latency**: `histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le, endpoint))`
- **Job Processing Time**: `histogram_quantile(0.95, sum(rate(job_processing_duration_seconds_bucket[1h])) by (le))`
- **Job Success Rate**: `sum(jobs_completed_total) / (sum(jobs_completed_total) + sum(jobs_failed_total))`

### Storage Metrics

Storage-related metrics:

- **Storage Usage by Bucket**: `minio_bucket_usage_bytes`
- **Object Count by Bucket**: `minio_bucket_objects_count`
- **Upload Rate**: `rate(minio_s3_requests_total{api="PutObject"}[5m])`
- **Download Rate**: `rate(minio_s3_requests_total{api="GetObject"}[5m])`

## Integration with Other Components

### API Integration

The API service exposes metrics about:

- API request volume and latency
- Job creation and status updates
- Error rates and types

```python
# API health endpoint that also reports metrics
@app.route('/api/health')
def health():
    # Check database connection
    db_status = check_database_connection()
    
    # Check MinIO connection
    minio_status = check_minio_connection()
    
    # Check reconstruction service
    recon_status = check_reconstruction_service()
    
    # Track health check metrics
    HEALTH_CHECK.labels(component='database', status=db_status).inc()
    HEALTH_CHECK.labels(component='minio', status=minio_status).inc()
    HEALTH_CHECK.labels(component='reconstruction', status=recon_status).inc()
    
    # Overall status
    overall_status = all([db_status == 'healthy', 
                          minio_status == 'healthy', 
                          recon_status == 'healthy'])
    
    return jsonify({
        'status': 'healthy' if overall_status else 'unhealthy',
        'components': {
            'database': db_status,
            'minio': minio_status,
            'reconstruction': recon_status
        },
        'timestamp': datetime.now().isoformat()
    }), 200 if overall_status else 500
```

### Reconstruction Service Integration

The reconstruction service monitors:

- Processing stages and durations
- Resource utilization during processing
- Error frequency and types

```python
# Reconstruction service metrics instrumentation
class ReconstructionMetrics:
    def __init__(self):
        # Processing stage durations
        self.stage_duration = Histogram(
            'reconstruction_stage_duration_seconds',
            'Duration of each reconstruction stage',
            ['stage', 'dataset_type']
        )
        
        # Memory usage during processing
        self.memory_usage = Gauge(
            'reconstruction_memory_usage_bytes',
            'Memory usage during reconstruction',
            ['stage']
        )
        
        # Model metrics
        self.point_count = Histogram(
            'reconstruction_point_cloud_size',
            'Number of points in generated point clouds',
            ['dataset_type']
        )
        
        self.mesh_face_count = Histogram(
            'reconstruction_mesh_face_count',
            'Number of faces in generated meshes',
            ['dataset_type']
        )
        
        # Error counters
        self.errors = Counter(
            'reconstruction_errors_total',
            'Number of errors during reconstruction',
            ['stage', 'error_type']
        )

metrics = ReconstructionMetrics()

# Usage in reconstruction pipeline
def process_images(job_id, dataset_type):
    try:
        # Feature extraction stage
        start_time = time.time()
        memory_before = get_process_memory()
        
        extract_features(job_id)
        
        memory_after = get_process_memory()
        metrics.memory_usage.labels('feature_extraction').set(memory_after)
        metrics.stage_duration.labels('feature_extraction', dataset_type).observe(
            time.time() - start_time
        )
        
        # Additional stages...
    except Exception as e:
        error_type = type(e).__name__
        metrics.errors.labels('feature_extraction', error_type).inc()
        raise
```

### Airflow Integration

Airflow metrics include:

- DAG run statistics
- Task success/failure rates
- Processing times

These metrics are collected by Airflow's built-in StatsD or Prometheus exporters.

## Alerting and Notifications

### Alert Rules

Prometheus alert rules monitor for critical conditions:

```yaml
# alert_rules.yml (excerpt)
groups:
- name: e2e3d_alerts
  rules:
  - alert: HighCPUUsage
    expr: avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) < 0.1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High CPU usage on {{ $labels.instance }}"
      description: "CPU usage is above 90% for more than 5 minutes"

  - alert: HighAPILatency
    expr: histogram_quantile(0.95, sum(rate(api_request_duration_seconds_bucket[5m])) by (le)) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High API latency"
      description: "95th percentile API latency is above 1 second for 5 minutes"

  - alert: JobFailureRateHigh
    expr: sum(rate(jobs_failed_total[1h])) / sum(rate(jobs_created_total[1h])) > 0.1
    for: 15m
    labels:
      severity: critical
    annotations:
      summary: "High job failure rate"
      description: "Job failure rate is above 10% for the last 15 minutes"
```

### Notification Channels

Grafana supports multiple notification channels:

- Email notifications
- Slack alerts
- PagerDuty integration
- Webhook callbacks

## Analyzing Metrics for Optimization

### Performance Bottleneck Identification

Using metrics to identify bottlenecks:

1. **Latency Analysis**: Examine request duration metrics to find slow components
2. **Resource Saturation**: Look for high CPU, memory, or disk utilization
3. **Queue Backlog**: Monitor job queue depth and processing times
4. **Error Correlation**: Connect spikes in errors with system events

### Capacity Planning

Metrics-based capacity planning:

1. **Growth Trending**: Project resource needs based on usage patterns
2. **Peak Analysis**: Identify peak usage periods and required headroom
3. **Resource Utilization**: Balance CPU, memory, storage, and network resources
4. **Scaling Triggers**: Determine thresholds for scaling actions

## Best Practices

### Effective Monitoring

Guidelines for effective monitoring:

- **Focus on User Experience**: Monitor what affects users directly
- **Alert on Symptoms, Not Causes**: Alert on user-facing issues, then diagnose
- **Use Rate, Error, Duration (RED) Method**: For service monitoring
- **Use Four Golden Signals**: Latency, traffic, errors, and saturation

### Dashboard Design

Principles for effective dashboards:

- **Hierarchy of Information**: Overview first, then details
- **Consistent Layouts**: Maintain consistency across dashboards
- **Time Alignment**: Ensure all graphs use the same time scale
- **Context**: Provide context with thresholds and historical norms
- **Annotations**: Mark significant events on dashboards

### Alert Management

Best practices for alerting:

- **Avoid Alert Fatigue**: Only alert on actionable conditions
- **Define Clear Ownership**: Ensure each alert has a responsible team
- **Include Runbooks**: Link alerts to troubleshooting procedures
- **Tune Thresholds**: Regularly review and adjust alert thresholds

## Troubleshooting with Metrics

### Common Issues

Using metrics to diagnose common problems:

- **High API Latency**: Check database performance, backend services, and resource contention
- **Job Failures**: Examine error rates by job type and error category
- **Resource Exhaustion**: Look for components approaching resource limits
- **Storage Bottlenecks**: Monitor I/O rates and storage capacity

### Correlation Analysis

Techniques for correlating metrics:

- **Time-Series Alignment**: Compare metrics over the same time period
- **Heatmaps**: Visualize distribution patterns and outliers
- **Cross-Component Analysis**: Connect frontend latency with backend processing
- **Causal Analysis**: Determine which metrics lead and which follow

## Advanced Topics

### Custom Metrics

Developing custom metrics for E2E3D-specific insights:

- **Domain-Specific Metrics**: 3D mesh quality, texture resolution, point cloud density
- **Process-Level Metrics**: Stage-by-stage performance metrics
- **Hardware Utilization**: GPU usage, specialized hardware performance
- **Quality Metrics**: Reconstruction quality scores

### Distributed Tracing

Adding tracing for detailed performance analysis:

- **OpenTelemetry Integration**: Standardized approach to tracing
- **Trace Context Propagation**: Tracking requests across services
- **Span Analysis**: Breaking down processing into measurable spans
- **Trace Sampling**: Balancing telemetry detail with overhead

## Conclusion

The E2E3D monitoring and metrics system provides essential visibility into the platform's operation, enabling early problem detection, performance optimization, and capacity planning. By leveraging Prometheus and Grafana along with comprehensive instrumentation, the system delivers actionable insights that improve reliability and user experience. Understanding and utilizing these metrics effectively is key to maintaining a healthy, high-performing E2E3D deployment. 