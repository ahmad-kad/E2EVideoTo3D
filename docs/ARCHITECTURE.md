# E2E3D System Architecture

This document provides a comprehensive overview of the E2E3D system architecture, explaining how all the components work together to provide a scalable and reliable 3D reconstruction service.

## Overview

E2E3D is a containerized application for end-to-end 3D reconstruction from image sets. The system is designed to be scalable, reliable, and easy to deploy in various environments. It consists of several interconnected components that work together to process reconstruction jobs, store results, and provide monitoring and metrics.

## System Components

The E2E3D system consists of the following key components:

### 1. API Service

The API service provides a RESTful interface for interacting with the E2E3D system. It handles incoming requests for reconstruction jobs, job status queries, and result retrieval.

**Key features:**
- RESTful HTTP endpoints for job submission and management
- Job status tracking and result retrieval
- Metrics collection and reporting
- Error handling and validation

**Technologies:**
- Flask (Python web framework)
- Gunicorn (WSGI HTTP Server)

### 2. Reconstruction Service

The reconstruction service is the core component responsible for processing 3D reconstruction jobs. It takes input images and produces 3D models, point clouds, and texture maps.

**Key features:**
- Processes incoming reconstruction jobs
- Supports different quality levels (low, medium, high)
- Handles both CPU and GPU processing
- Generates various output formats

**Technologies:**
- Python
- OpenCV
- PyTorch
- Open3D

### 3. Object Storage (MinIO)

MinIO provides object storage for input images and reconstruction results. It is compatible with Amazon S3 API and offers high performance and scalability.

**Key features:**
- Stores input image sets
- Stores reconstruction results (meshes, textures, point clouds)
- Provides access control and versioning
- Offers API for programmatic access

**Technologies:**
- MinIO (S3-compatible object storage)

### 4. Metrics and Monitoring

The metrics system collects and exposes performance and operational metrics from the E2E3D services, enabling monitoring and alerting.

**Key features:**
- Collects service-level metrics
- Tracks job processing statistics
- Exposes metrics for Prometheus scraping
- Enables alerting based on thresholds

**Technologies:**
- Prometheus (time-series database for metrics)
- Grafana (visualization and dashboarding)

### 5. Reverse Proxy (Nginx)

Nginx serves as a reverse proxy, routing external requests to the appropriate internal services and handling SSL termination.

**Key features:**
- Routes API requests to the API service
- Serves static content
- Handles SSL termination
- Provides basic rate limiting and security

**Technologies:**
- Nginx

### 6. Database (PostgreSQL)

PostgreSQL stores metadata about jobs, users, and system state.

**Key features:**
- Stores job metadata and status
- Manages user accounts and authentication
- Tracks system state and configuration
- Provides data persistence

**Technologies:**
- PostgreSQL

### 7. Task Queue (Redis)

Redis provides a lightweight message queue for job coordination.

**Key features:**
- Manages job queues
- Facilitates communication between components
- Provides temporary data caching
- Enables horizontal scaling of workers

**Technologies:**
- Redis

### 8. Workflow Orchestration (Airflow)

Apache Airflow manages complex reconstruction workflows, especially for batch processing.

**Key features:**
- Defines and manages reconstruction workflows
- Schedules and monitors job execution
- Handles retries and error recovery
- Provides visibility into workflow state

**Technologies:**
- Apache Airflow

## Data Flow

### 1. Job Submission

1. A client submits a reconstruction job via the API
2. The API validates the request and creates a job entry
3. The job is submitted to the reconstruction service
4. The reconstruction service begins processing the job

### 2. Job Processing

1. The reconstruction service loads input images from the specified path
2. It performs image preprocessing and feature extraction
3. It reconstructs a sparse 3D point cloud
4. It generates a dense point cloud
5. It creates a mesh from the point cloud
6. It applies texture mapping to the mesh
7. It saves all outputs to the output directory

### 3. Results Storage

1. The reconstruction service saves results to the local filesystem
2. The results are then uploaded to MinIO for persistent storage
3. Metadata about the job and results is stored in the database

### 4. Result Retrieval

1. A client requests job results via the API
2. The API retrieves the job status and result locations
3. The API returns a list of result files with URLs
4. The client can download individual files via the provided URLs

## Component Interactions

### API Service and Reconstruction Service

The API service communicates with the reconstruction service to submit jobs and retrieve status information. This interaction happens through subprocess calls and filesystem operations.

### Reconstruction Service and MinIO

The reconstruction service uploads completed job results to MinIO for persistent storage. This happens via the MinIO client library or command-line interface.

### API Service and MinIO

The API service retrieves job results from MinIO when a client requests them. It provides signed URLs for direct download access.

### Metrics and Prometheus/Grafana

All components expose metrics that are scraped by Prometheus. Grafana visualizes these metrics in dashboards.

## Deployment Architecture

E2E3D is designed to be deployed using Docker Compose for development and testing, and Kubernetes for production environments.

### Docker Compose Deployment

The Docker Compose setup includes:
- API service container
- Reconstruction service container
- MinIO container
- PostgreSQL container
- Redis container
- Airflow containers (webserver, scheduler, worker)
- Prometheus container
- Grafana container
- Nginx container

All containers are connected via a Docker network, and persistent data is stored in Docker volumes.

### Kubernetes Deployment

In a Kubernetes deployment:
- Each component runs in its own pod
- Services expose the components within the cluster
- Ingress resources manage external access
- Persistent volumes provide storage
- ConfigMaps and Secrets manage configuration
- Horizontal Pod Autoscalers manage scaling

## Scaling Considerations

### Horizontal Scaling

The E2E3D system supports horizontal scaling in several ways:
- Multiple reconstruction service instances can process jobs in parallel
- API service can be scaled to handle increased request load
- MinIO can be configured as a distributed cluster for increased storage capacity

### Vertical Scaling

Components can also be vertically scaled by:
- Increasing CPU and memory allocations
- Using more powerful GPU hardware for reconstruction
- Optimizing database performance through hardware upgrades

## Security Considerations

### Authentication and Authorization

- API endpoints are protected by authentication
- JWT tokens are used for API authorization
- MinIO access is controlled by access keys
- Database access is restricted by username/password

### Data Security

- All communications can be encrypted using SSL/TLS
- Sensitive data is encrypted at rest
- Access to input data and results is restricted to authorized users

### Network Security

- Containers expose only necessary ports
- Internal components are not directly accessible from outside
- Firewall rules restrict external access to public endpoints only

## Monitoring and Maintenance

### Health Checks

All components expose health check endpoints that can be used to verify their operational status. These are checked by Kubernetes liveness and readiness probes.

### Metrics and Alerts

- Service-level metrics track system performance
- Job-level metrics track processing stats
- Alerts are configured for important thresholds
- Dashboards provide operational visibility

### Logging

- All components emit structured logs
- Logs are aggregated and centrally stored
- Log levels can be adjusted as needed
- Log retention policies manage storage usage

## Disaster Recovery

### Backup Strategy

- Regular backups of database data
- Backups of MinIO objects
- Configuration backups
- Automated backup verification

### Recovery Procedures

- Database restore procedures
- MinIO recovery process
- Service redeployment steps
- Data consistency verification

## Future Enhancements

### Planned Improvements

- Distributed processing for very large jobs
- Real-time progress updates via WebSockets
- Enhanced GPU utilization for faster processing
- Advanced quality options for different use cases

### Integration Opportunities

- Integration with computer vision AI services
- Webhooks for workflow integration
- SDK for programmatic access
- Mobile app for direct capture and reconstruction 