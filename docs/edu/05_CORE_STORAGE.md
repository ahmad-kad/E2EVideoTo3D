# Storage System

## Introduction

The storage system is a critical component of the E2E3D platform, responsible for efficiently storing and retrieving various types of data throughout the reconstruction process. This document explains the storage architecture, components, and best practices for managing data in the E2E3D system.

## Storage Concepts

### Object Storage vs. File Storage

Two primary storage paradigms are used in E2E3D:

**File Storage**:
- Hierarchical directory structure
- Familiar for most users
- Good for direct access during processing
- Examples: Local file system, NFS

**Object Storage**:
- Flat namespace with buckets and objects
- High scalability and durability
- HTTP-based access
- Examples: MinIO, Amazon S3, Google Cloud Storage

### Data Lifecycle

Data in E2E3D goes through several stages:

1. **Input Data**: Original images and configuration
2. **Intermediate Data**: Temporary processing artifacts
3. **Output Data**: Final 3D models and related files
4. **Metadata**: Information about jobs and results
5. **Archive Data**: Long-term storage of completed jobs

## Storage Architecture

### Components

The E2E3D storage system consists of:

1. **MinIO**: S3-compatible object storage for durable data
   - Input bucket: Stores original image sets
   - Output bucket: Stores final reconstruction results
   - Models bucket: Stores pre-trained models and configuration

2. **Local File System**: Used during active processing
   - Temporary directories for each job
   - Fast access for computation-heavy tasks
   - Automatically cleaned up after processing

3. **PostgreSQL**: Stores metadata about jobs and results
   - Job tracking and status
   - Result locations and statistics
   - System configuration

### Data Flow

A typical data flow through the storage system:

1. Input images are uploaded to MinIO input bucket
2. When processing starts, images are copied to local storage
3. Processing generates intermediate files in local storage
4. Final results are saved to both local storage and MinIO output bucket
5. Metadata is stored in PostgreSQL
6. Temporary local files are cleaned up

## Implementation Details

### MinIO Configuration

MinIO is configured with:

- Multiple buckets for different data types
- Access controls for security
- Versioning for critical data
- Lifecycle policies for data management

```yaml
# MinIO Docker Compose configuration (excerpt)
minio:
  image: minio/minio:latest
  container_name: e2e3d-minio
  command: server --console-address ":9001" /data
  environment:
    - MINIO_ROOT_USER=${MINIO_ROOT_USER:-minioadmin}
    - MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD:-minioadmin}
  ports:
    - "9000:9000"
    - "9001:9001"
  volumes:
    - minio-data:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
```

### Directory Structure

The standard directory structure for local file processing:

```
/app/data/
├── input/
│   ├── [dataset1]/
│   ├── [dataset2]/
│   └── ...
├── output/
│   ├── [job_id1]/
│   │   ├── [job_id1]_[timestamp]/
│   │   │   ├── mesh/
│   │   │   │   └── reconstructed_mesh.obj
│   │   │   ├── textures/
│   │   │   │   └── texture.png
│   │   │   ├── pointcloud/
│   │   │   │   └── pointcloud.ply
│   │   │   ├── logs/
│   │   │   ├── temp/
│   │   │   ├── metadata.json
│   │   │   └── SUCCESS
│   │   └── ...
│   └── ...
└── temp/
    └── [job_id]_[timestamp]/
        └── ... (intermediate files)
```

### File Formats

Common file formats used in E2E3D:

- **OBJ**: 3D mesh with material references
- **MTL**: Material definitions for OBJ files
- **PLY**: Point cloud data
- **PNG/JPG**: Texture maps and input images
- **JSON**: Metadata and configuration
- **LOG**: Processing logs

## Integration with Other Components

### API Integration

The storage system integrates with the API by:

- Providing endpoints for file upload and download
- Generating pre-signed URLs for direct access
- Reporting storage statistics and availability

```python
# Example API code for generating download URLs
@app.route('/api/job/<job_id>/results')
def get_job_results(job_id):
    # Get job details from database
    job = Job.query.filter_by(id=job_id).first_or_404()
    
    # Generate MinIO URLs with 24-hour expiration
    minio_client = get_minio_client()
    mesh_url = minio_client.presigned_get_object(
        'output',
        f'{job_id}/mesh/reconstructed_mesh.obj',
        expires=timedelta(hours=24)
    )
    texture_url = minio_client.presigned_get_object(
        'output',
        f'{job_id}/textures/texture.png',
        expires=timedelta(hours=24)
    )
    
    return jsonify({
        'job_id': job_id,
        'status': job.status,
        'files': {
            'mesh': mesh_url,
            'texture': texture_url,
            # Additional files...
        }
    })
```

### Reconstruction Service Integration

The reconstruction service accesses storage through:

- Direct file system access for active processing
- MinIO client for input/output
- Automatic synchronization between local and object storage

```python
# Example reconstruction service code for file handling
def process_job(job_id, input_path, output_path):
    # Ensure directories exist
    os.makedirs(output_path, exist_ok=True)
    
    # Process files
    # ...
    
    # Upload results to MinIO
    minio_client = get_minio_client()
    for root, dirs, files in os.walk(output_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, output_path)
            object_name = f"{job_id}/{relative_path}"
            
            minio_client.fput_object(
                'output',
                object_name,
                file_path
            )
    
    # Create SUCCESS marker
    with open(os.path.join(output_path, 'SUCCESS'), 'w') as f:
        f.write(f"Job completed successfully at {datetime.now().isoformat()}")
    
    # Upload SUCCESS marker
    minio_client.fput_object(
        'output',
        f"{job_id}/SUCCESS",
        os.path.join(output_path, 'SUCCESS')
    )
```

### Airflow Integration

Airflow interacts with storage through:

- Sensors that monitor for file presence
- Operators that read and write data
- XComs for small data exchange between tasks

## Performance Optimization

### Caching

E2E3D implements several caching strategies:

- **Local File Cache**: Frequently used files kept on local storage
- **Read-Through Cache**: Automatically fetching from MinIO to local storage
- **Write-Back Cache**: Asynchronous uploads to MinIO

### Compression

Data compression techniques:

- **Image Compression**: JPEG/PNG optimizations for textures
- **Mesh Simplification**: Reducing polygon count while preserving detail
- **Point Cloud Downsampling**: Reducing point density for large point clouds

### Parallel Access

Approaches to parallel storage access:

- **Concurrent Uploads/Downloads**: Multiple threads for I/O operations
- **Chunked Transfers**: Breaking large files into manageable chunks
- **Batch Operations**: Grouping small operations for efficiency

## Security Considerations

### Authentication and Authorization

Storage security measures:

- **Access Keys**: Secure access to MinIO with access/secret keys
- **TLS Encryption**: Encrypted connections for data transfers
- **Role-Based Access**: Different permissions for different user roles

### Data Protection

Data protection strategies:

- **Versioning**: Keeping multiple versions of critical files
- **Backups**: Regular backups of important data
- **Checksums**: Verifying file integrity during transfers

## Monitoring and Maintenance

### Monitoring

Storage monitoring includes:

- **Space Usage**: Tracking storage capacity and utilization
- **I/O Performance**: Monitoring read/write speeds
- **Error Rates**: Tracking storage-related errors
- **Access Patterns**: Understanding how storage is being used

### Maintenance Tasks

Routine maintenance activities:

- **Cleanup**: Removing temporary and unnecessary files
- **Defragmentation**: Optimizing storage layout
- **Health Checks**: Verifying storage system health
- **Scaling**: Adding capacity as needed

## Best Practices

### Organizing Data

Guidelines for data organization:

- **Consistent Naming**: Use consistent naming conventions
- **Hierarchical Structure**: Organize data in logical hierarchies
- **Metadata**: Use metadata to describe and classify data
- **Versioning**: Implement versioning for important files

### Optimizing Storage Usage

Strategies for efficient storage:

- **Right-Sizing**: Store data at appropriate resolution/quality
- **Deduplication**: Avoid storing duplicate data
- **Archiving**: Moving old data to lower-cost storage
- **Cleanup Policies**: Automatically removing unnecessary data

### Handling Large Datasets

Approaches for large data:

- **Streaming Processing**: Processing data as it streams, without full loading
- **Tiling**: Breaking large textures into smaller tiles
- **Level of Detail**: Multiple resolutions for different use cases
- **Selective Preservation**: Keeping only essential intermediate files

## Troubleshooting

Common storage issues and solutions:

- **Permission Problems**: Verify user/group permissions
- **Space Issues**: Check available storage and clean up unnecessary files
- **Performance Bottlenecks**: Identify I/O bottlenecks and optimize access patterns
- **Data Corruption**: Use checksums and versioning to recover from corruption

## Conclusion

The E2E3D storage system provides a robust, scalable foundation for managing the diverse data needs of 3D reconstruction. By combining local file storage for performance with object storage for durability, the system achieves a balance of speed, reliability, and accessibility. Understanding the storage architecture and following best practices allows users to effectively manage data throughout the reconstruction process. 