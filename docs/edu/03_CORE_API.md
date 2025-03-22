# API and Job Management

## Introduction

The API and job management system forms the interface layer of the E2E3D platform, allowing users and other systems to interact with the reconstruction service. This document covers the design, implementation, and usage of the API, as well as the underlying job management system.

## API Concepts

### RESTful API Design

REST (Representational State Transfer) is an architectural style for designing networked applications. Key principles of REST that our API follows include:

- **Statelessness**: Each request contains all the information needed to complete it
- **Resource-Based**: API endpoints represent resources (e.g., jobs, models)
- **HTTP Methods**: Using standard HTTP methods (GET, POST, PUT, DELETE) for operations
- **Standard Formats**: Using JSON for data exchange
- **Status Codes**: Using HTTP status codes to indicate request outcomes

### Job Management

Job management involves:

- **Job Creation**: Accepting and validating reconstruction requests
- **Job Tracking**: Monitoring and reporting job status
- **Job Control**: Allowing users to pause, resume, or cancel jobs
- **Result Handling**: Storing and providing access to job outputs
- **Error Management**: Detecting, reporting, and recovering from errors

## API Endpoints

The E2E3D API exposes several key endpoints:

### Reconstruction Jobs

- `POST /api/reconstruct`: Submit a new reconstruction job
- `GET /api/job/{job_id}`: Get status of a specific job
- `GET /api/jobs`: List all jobs or filter by status
- `DELETE /api/job/{job_id}`: Cancel a job
- `GET /api/job/{job_id}/results`: Get links to job results

### System Management

- `GET /api/metrics`: Get system metrics and statistics
- `GET /api/health`: Check system health status
- `GET /api/config`: Get system configuration

## Request and Response Formats

### Job Submission

```json
POST /api/reconstruct
{
  "image_set_path": "/app/data/input/SampleImages",
  "quality": "medium",
  "job_id": "sample_job_123",
  "use_gpu": true,
  "notify_url": "https://example.com/callback"
}
```

### Job Status Response

```json
GET /api/job/sample_job_123
{
  "job_id": "sample_job_123",
  "status": "processing",
  "progress": 65,
  "stage": "mesh_generation",
  "start_time": "2025-03-22T01:32:17Z",
  "estimated_completion": "2025-03-22T02:15:00Z",
  "error": null
}
```

### Job Results Response

```json
GET /api/job/sample_job_123/results
{
  "job_id": "sample_job_123",
  "status": "completed",
  "output_dir": "/app/data/output/sample_job_123",
  "files": {
    "mesh": "/output/sample_job_123/mesh/reconstructed_mesh.obj",
    "texture": "/output/sample_job_123/textures/texture.png",
    "pointcloud": "/output/sample_job_123/pointcloud/pointcloud.ply",
    "metadata": "/output/sample_job_123/metadata.json"
  },
  "minio_urls": {
    "mesh": "http://minio:9000/output/sample_job_123/mesh/reconstructed_mesh.obj",
    "texture": "http://minio:9000/output/sample_job_123/textures/texture.png",
    "pointcloud": "http://minio:9000/output/sample_job_123/pointcloud/pointcloud.ply",
    "metadata": "http://minio:9000/output/sample_job_123/metadata.json"
  }
}
```

## Implementation Details

### API Framework

The E2E3D API is built using:

- **Flask**: A lightweight Python web framework
- **Gunicorn**: WSGI HTTP server for production
- **NGINX**: Reverse proxy for routing and load balancing

### Job State Management

Jobs progress through several states:

1. **Submitted**: Job received but not yet started
2. **Queued**: Job in the processing queue
3. **Processing**: Job currently being processed
4. **Completed**: Job successfully finished
5. **Failed**: Job terminated with errors
6. **Cancelled**: Job cancelled by user request

### Concurrency and Scaling

The API and job management system handle concurrency through:

- **Worker Processes**: Multiple worker processes handle API requests
- **Job Queue**: Redis-based queue for job scheduling
- **Resource Management**: Limiting concurrent job execution based on system resources
- **Load Balancing**: Distributing requests across worker instances

## Security Considerations

The API implements several security measures:

- **Authentication**: API keys or token-based authentication for access control
- **Authorization**: Role-based permissions for different API operations
- **Input Validation**: Strict validation of all input parameters
- **Rate Limiting**: Preventing abuse through request rate limitations
- **Secure Connections**: HTTPS for all communications

## Integration with Other Components

### Reconstruction Service Integration

The API communicates with the reconstruction service through:

- **Command Execution**: Launching reconstruction processes with appropriate parameters
- **Status Monitoring**: Checking job status through filesystem markers or IPC
- **Result Collection**: Gathering and organizing reconstruction outputs

### Airflow Integration

For complex workflows, the API can delegate to Airflow:

- **DAG Triggering**: Initiating Airflow DAGs for workflow execution
- **Status Synchronization**: Keeping job status in sync with Airflow task status
- **Result Handling**: Processing and exposing results from Airflow tasks

### Storage Integration

The API interacts with the storage system:

- **Input Validation**: Checking input data availability and integrity
- **Output Management**: Organizing and storing job outputs
- **URL Generation**: Creating access URLs for result retrieval

## Error Handling and Resilience

The API implements robust error handling:

- **Graceful Degradation**: Maintaining core functionality during partial system failures
- **Retry Mechanisms**: Automatically retrying failed operations with exponential backoff
- **Detailed Error Reporting**: Providing meaningful error messages and logs
- **Circuit Breaking**: Preventing cascading failures through circuit breakers

## Extending the API

Guidelines for adding new API features:

- **Endpoint Design**: Follow RESTful principles for new endpoints
- **Versioning**: Use API versioning for backward compatibility
- **Documentation**: Update OpenAPI/Swagger documentation for new features
- **Testing**: Create unit and integration tests for new endpoints

## Client Integration

Examples of client integration:

### Python Client

```python
import requests

# Submit a new job
response = requests.post(
    "http://localhost/api/reconstruct",
    json={
        "image_set_path": "/app/data/input/SampleImages",
        "quality": "medium",
        "job_id": "sample_job_123"
    }
)
job_id = response.json()["job_id"]

# Check job status
status_response = requests.get(f"http://localhost/api/job/{job_id}")
print(f"Job status: {status_response.json()['status']}")

# Get results when complete
if status_response.json()["status"] == "completed":
    results = requests.get(f"http://localhost/api/job/{job_id}/results")
    print(f"Mesh URL: {results.json()['files']['mesh']}")
```

### cURL Examples

```bash
# Submit a job
curl -X POST "http://localhost/api/reconstruct" \
  -H "Content-Type: application/json" \
  -d '{"image_set_path": "/app/data/input/SampleImages", "quality": "medium", "job_id": "sample_job_123"}'

# Check status
curl -X GET "http://localhost/api/job/sample_job_123"

# Get results
curl -X GET "http://localhost/api/job/sample_job_123/results"
```

## Conclusion

The API and job management system provides a flexible, robust interface to the E2E3D reconstruction capabilities. By following RESTful design principles and implementing comprehensive job tracking, the system enables easy integration with other applications and workflows. The combination of well-defined endpoints, clear response formats, and robust error handling makes the API a powerful tool for both human users and automated systems. 