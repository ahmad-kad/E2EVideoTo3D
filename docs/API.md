# E2E3D API Documentation

This document describes the HTTP API for the E2E3D reconstruction service.

## Base URL

All API endpoints are accessed through the base URL:

```
http://localhost/api
```

This can be configured in your environment to point to a different host or port as needed.

## Health Check

### GET /api/health

Checks if the API service is running correctly.

**Response:**

```json
{
  "status": "healthy"
}
```

## Metrics

### GET /api/metrics

Checks if the metrics server is available.

**Response (metrics available):**

```json
{
  "status": "available",
  "port": 9101
}
```

**Response (metrics unavailable):**

```json
{
  "status": "unavailable",
  "reason": "Metrics not enabled"
}
```

## Job Management

### POST /api/reconstruct

Submits a new reconstruction job.

**Request Body:**

```json
{
  "image_set_path": "/app/data/input/my_image_set",
  "quality": "medium",
  "job_id": "my_job_123"
}
```

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `image_set_path` | string | Yes | Path to the directory containing input images |
| `quality` | string | No | Quality setting for reconstruction: "low", "medium", or "high". Default: "medium" |
| `job_id` | string | No | Unique identifier for the job. If not provided, a random ID will be generated |
| `use_gpu` | boolean | No | Whether to use GPU for reconstruction. If not provided, auto-detection is used |
| `upload` | boolean | No | Whether to upload results to object storage automatically |
| `notify_url` | string | No | Webhook URL to notify when job completes |

**Response (success):**

```json
{
  "status": "submitted",
  "job_id": "my_job_123"
}
```

**Response (error):**

```json
{
  "error": "image_set_path is required"
}
```

### GET /api/jobs

Lists all jobs and their status.

**Response:**

```json
{
  "jobs": {
    "job_001": {
      "status": "running",
      "start_time": 1715386012.4529,
      "elapsed": 45.2,
      "output_dir": "/app/data/output/job_001"
    },
    "job_002": {
      "status": "completed",
      "start_time": 1715386000.1234,
      "end_time": 1715386060.5678,
      "duration": 60.4444,
      "output_dir": "/app/data/output/job_002"
    },
    "job_003": {
      "status": "failed",
      "start_time": 1715386100.9876,
      "end_time": 1715386120.5432,
      "duration": 19.5556,
      "output_dir": "/app/data/output/job_003",
      "error": "Reconstruction failed: insufficient input images"
    }
  }
}
```

### GET /api/job/{job_id}

Gets the status of a specific job.

**Response (running job):**

```json
{
  "job_id": "job_001",
  "status": "running",
  "start_time": 1715386012.4529,
  "elapsed": 45.2,
  "output_dir": "/app/data/output/job_001"
}
```

**Response (completed job):**

```json
{
  "job_id": "job_002",
  "status": "completed",
  "start_time": 1715386000.1234,
  "end_time": 1715386060.5678,
  "duration": 60.4444,
  "output_dir": "/app/data/output/job_002"
}
```

**Response (failed job):**

```json
{
  "job_id": "job_003",
  "status": "failed",
  "start_time": 1715386100.9876,
  "end_time": 1715386120.5432,
  "duration": 19.5556,
  "output_dir": "/app/data/output/job_003",
  "error": "Reconstruction failed: insufficient input images"
}
```

**Response (job not found):**

```json
{
  "error": "Job job_999 not found"
}
```

### POST /api/job/{job_id}/cancel

Cancels a running job.

**Response (success):**

```json
{
  "status": "cancelled",
  "job_id": "job_001"
}
```

**Response (job not found or not running):**

```json
{
  "error": "Job job_999 not found or not running"
}
```

### GET /api/job/{job_id}/results

Gets a list of result files for a completed job.

**Response (success):**

```json
{
  "job_id": "job_002",
  "result_dir": "job_002/job_002_20230426_125423",
  "files": [
    {
      "path": "job_002/job_002_20230426_125423/mesh/reconstructed_mesh.obj",
      "type": "obj",
      "size": 1048576,
      "url": "/api/file/job_002/job_002_20230426_125423/mesh/reconstructed_mesh.obj"
    },
    {
      "path": "job_002/job_002_20230426_125423/textures/texture_map.jpg",
      "type": "jpg",
      "size": 524288,
      "url": "/api/file/job_002/job_002_20230426_125423/textures/texture_map.jpg"
    },
    {
      "path": "job_002/job_002_20230426_125423/pointcloud/pointcloud.ply",
      "type": "ply",
      "size": 2097152,
      "url": "/api/file/job_002/job_002_20230426_125423/pointcloud/pointcloud.ply"
    }
  ]
}
```

**Response (job not found):**

```json
{
  "error": "Job directory for job_999 not found"
}
```

**Response (job not completed successfully):**

```json
{
  "error": "Job job_003 did not complete successfully"
}
```

### GET /api/file/{filepath}

Downloads a specific file.

**Response:**

The file contents as an attachment with appropriate Content-Type header.

**Response (file not found):**

```json
{
  "error": "File job_999/mesh/reconstructed_mesh.obj not found"
}
```

## Error Handling

All API endpoints return appropriate HTTP status codes:

- `200 OK`: Successful request
- `400 Bad Request`: Invalid request parameters
- `404 Not Found`: Requested resource not found
- `500 Internal Server Error`: Server-side error

Error responses include a JSON object with an `error` field containing a description of the error.

## Metrics Integration

The API integrates with Prometheus for metrics collection. The following metrics are available:

- `reconstruction_total`: Total number of reconstruction jobs processed
- `reconstruction_success`: Number of successful reconstruction jobs
- `reconstruction_failure`: Number of failed reconstruction jobs
- `e2e3d_active_jobs`: Number of currently active reconstruction jobs
- `e2e3d_job_duration_seconds`: Total time spent processing jobs (labeled by job_id and status)

Metrics are accessible at `http://localhost:9101/metrics`. 