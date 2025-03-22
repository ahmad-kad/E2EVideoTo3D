# E2E3D Metrics Documentation

This document describes the metrics system used in the E2E3D reconstruction service.

## Overview

E2E3D uses Prometheus for metrics collection, which provides a powerful and flexible way to monitor the system's performance and health. The metrics are exposed via an HTTP endpoint and can be scraped by a Prometheus server for storage and analysis. Grafana can then be used to visualize these metrics through dashboards.

## Metrics Server

The metrics server runs on port 9101 by default and exposes metrics in the Prometheus format. The server is automatically started when the API service is started, provided that metrics are enabled via the `ENABLE_METRICS` environment variable.

## Available Metrics

### Reconstruction Job Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `reconstruction_total` | Counter | Total number of reconstruction jobs processed | None |
| `reconstruction_success` | Counter | Number of successful reconstruction jobs | None |
| `reconstruction_failure` | Counter | Number of failed reconstruction jobs | None |
| `e2e3d_active_jobs` | Gauge | Number of currently active reconstruction jobs | None |
| `e2e3d_job_duration_seconds` | Counter | Total time spent processing jobs | `job_id`, `status` |

### System Metrics

In addition to the custom metrics defined above, the Prometheus client library automatically exposes several system metrics:

| Metric Name | Type | Description |
|-------------|------|-------------|
| `process_cpu_seconds_total` | Counter | Total user and system CPU time spent in seconds |
| `process_open_fds` | Gauge | Number of open file descriptors |
| `process_max_fds` | Gauge | Maximum number of open file descriptors |
| `process_virtual_memory_bytes` | Gauge | Virtual memory size in bytes |
| `process_resident_memory_bytes` | Gauge | Resident memory size in bytes |
| `process_start_time_seconds` | Gauge | Start time of the process since unix epoch in seconds |

## Enabling Metrics

Metrics collection is enabled by setting the `ENABLE_METRICS` environment variable to `true`. This can be done in the Docker Compose file or directly in the environment where the service is running.

For example, in the Docker Compose file:

```yaml
services:
  reconstruction-service:
    environment:
      - ENABLE_METRICS=true
```

## Accessing Metrics

The metrics are exposed at the following endpoint:

```
http://localhost:9101/metrics
```

If accessing from outside the Docker network, replace `localhost` with the appropriate host name or IP address.

## Prometheus Integration

### Configuring Prometheus

To configure Prometheus to scrape metrics from the E2E3D service, add the following job to your `prometheus.yml` configuration file:

```yaml
scrape_configs:
  - job_name: 'e2e3d'
    scrape_interval: 15s
    static_configs:
      - targets: ['reconstruction-service:9101']
```

If Prometheus is running outside the Docker network, replace `reconstruction-service` with the appropriate host name or IP address.

### Sample Prometheus Queries

Here are some useful Prometheus queries for monitoring the E2E3D service:

- Total number of jobs processed:
  ```
  reconstruction_total
  ```

- Success rate (percentage):
  ```
  (reconstruction_success / reconstruction_total) * 100
  ```

- Number of active jobs:
  ```
  e2e3d_active_jobs
  ```

- Average job duration:
  ```
  sum(e2e3d_job_duration_seconds) / count(e2e3d_job_duration_seconds)
  ```

- Job duration by status:
  ```
  sum(e2e3d_job_duration_seconds) by (status)
  ```

## Grafana Integration

### Setting Up Grafana

1. Add Prometheus as a data source in Grafana:
   - Name: Prometheus
   - Type: Prometheus
   - URL: http://prometheus:9090
   - Access: Server (default)

2. Import or create dashboards to visualize the metrics.

## Alerting

Prometheus can be configured to trigger alerts based on metric values. Here are some example alerting rules:

```yaml
groups:
  - name: E2E3D Alerts
    rules:
      - alert: HighFailureRate
        expr: (reconstruction_failure / reconstruction_total) > 0.1
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "High job failure rate"
          description: "The failure rate for reconstruction jobs is above 10% for the last 15 minutes."
      
      - alert: TooManyActiveJobs
        expr: e2e3d_active_jobs > 10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Too many active jobs"
          description: "There are more than 10 active reconstruction jobs for the last 5 minutes. The system might be overloaded."
```

## Troubleshooting

### Metrics Not Available

If the metrics endpoint returns a 404 or connection error:

1. Check that the `ENABLE_METRICS` environment variable is set to `true`.
2. Verify that the metrics server process is running:
   ```bash
   docker exec e2e3d-reconstruction-service ps aux | grep metrics
   ```
3. Verify that port 9101 is listening:
   ```bash
   docker exec e2e3d-reconstruction-service netstat -tulpn | grep 9101
   ```

### Prometheus Not Scraping Metrics

If Prometheus is not scraping metrics:

1. Check the Prometheus configuration:
   ```bash
   docker exec e2e3d-prometheus cat /etc/prometheus/prometheus.yml | grep reconstruction
   ```
2. Verify that Prometheus can reach the metrics endpoint:
   ```bash
   docker exec e2e3d-prometheus wget -q --spider http://reconstruction-service:9101/metrics
   ```
3. Check the Prometheus logs for any errors:
   ```bash
   docker logs e2e3d-prometheus
   ``` 