# Workflow Orchestration with Airflow

## Introduction

Apache Airflow is a platform to programmatically author, schedule, and monitor workflows. In the E2E3D system, Airflow provides the orchestration layer for managing complex reconstruction workflows, ensuring reliable execution, monitoring, and error handling. This document covers the fundamentals of Airflow and how it's implemented within the E2E3D system.

## Airflow Concepts

### Directed Acyclic Graphs (DAGs)

A DAG is a collection of tasks organized with dependencies and relationships to express how they should run:

- **Directed**: Each relationship has a direction - task A depends on task B
- **Acyclic**: No cycles (task A can't depend on task B if task B depends on task A)
- **Graph**: A collection of nodes (tasks) connected by directed edges (dependencies)

### Tasks and Operators

- **Task**: A defined unit of work within a DAG
- **Operator**: A template for a task, defining what work will be done
  - **PythonOperator**: Executes Python functions
  - **BashOperator**: Executes bash commands
  - **DockerOperator**: Executes tasks in Docker containers
  - **Custom Operators**: Specialized operators for specific tasks

### Task Instances

A task instance represents a specific run of a task at a point in time, with a specific state:

- **Scheduled**: Task is scheduled to run
- **Queued**: Task is in the queue to be picked up by a worker
- **Running**: Task is currently executing
- **Success**: Task completed successfully
- **Failed**: Task failed
- **Upstream Failed**: A task this task depends on failed
- **Skipped**: Task was skipped due to branching logic

### Executors

Executors determine how tasks are executed:

- **SequentialExecutor**: Runs one task at a time (development only)
- **LocalExecutor**: Runs multiple tasks on the local system
- **CeleryExecutor**: Distributes tasks across worker nodes (used in E2E3D)
- **KubernetesExecutor**: Runs tasks as pods in a Kubernetes cluster

## E2E3D Airflow Implementation

### Architecture

The E2E3D Airflow setup consists of:

1. **Airflow Webserver**: Web UI for monitoring and managing DAGs
2. **Airflow Scheduler**: Schedules and triggers task execution
3. **Airflow Workers**: Execute tasks (using CeleryExecutor)
4. **Postgres Database**: Stores Airflow metadata
5. **Redis**: Message broker for the Celery executor

### DAG Structure

The primary E2E3D reconstruction DAG follows this structure:

1. **Validation**: Validates input parameters and data
2. **Image Preparation**: Prepares images for reconstruction
3. **Feature Extraction**: Extracts features from images
4. **Camera Estimation**: Estimates camera positions
5. **Dense Reconstruction**: Generates dense point cloud
6. **Mesh Generation**: Creates 3D mesh from point cloud
7. **Texture Mapping**: Applies textures to the mesh
8. **Result Processing**: Organizes and stores results
9. **Notification**: Sends completion notifications

```python
# Example DAG structure (simplified)
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'e2e3d',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'e2e3d_reconstruction',
    default_args=default_args,
    schedule_interval=None,
    catchup=False,
) as dag:
    
    validate_task = PythonOperator(
        task_id='validate_inputs',
        python_callable=validate_reconstruction_inputs,
        op_kwargs={'job_id': '{{ dag_run.conf["job_id"] }}'},
    )
    
    prepare_images_task = PythonOperator(
        task_id='prepare_images',
        python_callable=prepare_images,
        op_kwargs={'job_id': '{{ dag_run.conf["job_id"] }}'},
    )
    
    # Additional tasks defined similarly
    
    # Set task dependencies
    validate_task >> prepare_images_task >> extract_features_task >> ...
```

### Dynamic DAG Generation

E2E3D uses dynamic DAG generation for flexibility:

- **Template DAGs**: Base DAG templates for different reconstruction workflows
- **Parameter Injection**: Job-specific parameters injected at runtime
- **Conditional Tasks**: Tasks included or excluded based on job requirements
- **Quality-Based Variations**: Different task configurations based on quality settings

### API Integration

Airflow integrates with the E2E3D API through:

1. **DAG Triggering**: API calls Airflow REST API to trigger DAGs
2. **Parameter Passing**: Job parameters passed as DAG run configuration
3. **Status Monitoring**: API polls Airflow for job status
4. **Result Retrieval**: DAG stores results in a location accessible to the API

## Monitoring and Management

### Web UI

The Airflow web interface provides:

- **DAG List**: Overview of all available DAGs
- **DAG Details**: Detailed view of a specific DAG
- **Task Instances**: Status and logs for task instances
- **Tree View**: Visualization of DAG runs over time
- **Graph View**: Visual representation of task dependencies

### Metrics and Alerting

E2E3D's Airflow implementation includes:

- **Prometheus Integration**: Metrics exported to Prometheus
- **Grafana Dashboards**: Visualization of Airflow metrics
- **Alert Rules**: Automatic alerts for failed tasks or delayed DAGs
- **Slack/Email Notifications**: Notifications for critical events

## Error Handling and Resilience

### Task Retries

Tasks can be configured with retry logic:

```python
task = PythonOperator(
    task_id='extract_features',
    python_callable=extract_features,
    retries=3,
    retry_delay=timedelta(minutes=5),
    retry_exponential_backoff=True,
)
```

### Error Callbacks

Custom error handlers provide detailed error reporting:

```python
def task_failure_callback(context):
    """Handle task failures with custom logic."""
    job_id = context['dag_run'].conf['job_id']
    task_id = context['task_instance'].task_id
    exception = context['exception']
    
    # Log error details
    logging.error(f"Task {task_id} failed for job {job_id}: {str(exception)}")
    
    # Update job status in external system
    update_job_status(job_id, 'failed', error=str(exception))
    
    # Send notification
    send_failure_notification(job_id, task_id, exception)

task = PythonOperator(
    task_id='extract_features',
    python_callable=extract_features,
    on_failure_callback=task_failure_callback,
)
```

### Recovery Mechanisms

The E2E3D Airflow implementation includes:

- **Checkpointing**: Saving intermediate results for recovery
- **State Recovery**: Ability to restart from the last successful task
- **Partial Results**: Delivering partial results when possible
- **Cleanup on Failure**: Proper resource cleanup even during failures

## Performance Optimization

### Resource Management

E2E3D optimizes Airflow resource usage through:

- **Pool Management**: Limiting concurrent execution of resource-intensive tasks
- **Queue Prioritization**: Assigning priorities to different job types
- **Worker Autoscaling**: Dynamically adjusting worker count based on load
- **Resource Allocation**: Assigning appropriate CPU/memory to tasks

### Execution Optimization

Performance is optimized through:

- **Task Granularity**: Balancing between too many small tasks and too few large ones
- **Parallelization**: Maximizing parallel execution where dependencies allow
- **Data Locality**: Minimizing data movement between tasks
- **Caching**: Reusing results from previous calculations where possible

## Advanced Usage

### Custom Operators

E2E3D extends Airflow with custom operators:

```python
class ReconstructionOperator(BaseOperator):
    """Custom operator for 3D reconstruction tasks."""
    
    template_fields = ['job_id', 'input_path', 'output_path']
    
    def __init__(
        self,
        job_id,
        input_path,
        output_path,
        quality='medium',
        use_gpu=False,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.job_id = job_id
        self.input_path = input_path
        self.output_path = output_path
        self.quality = quality
        self.use_gpu = use_gpu
        
    def execute(self, context):
        """Execute the reconstruction task."""
        # Task implementation
        logging.info(f"Starting reconstruction for job {self.job_id}")
        # ...
        return output_metadata
```

### Sensors

E2E3D uses sensors for conditional execution:

```python
class InputDataSensor(BaseSensorOperator):
    """Sensor that waits for input data to be ready."""
    
    template_fields = ['input_path', 'job_id']
    
    def __init__(self, input_path, job_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_path = input_path
        self.job_id = job_id
        
    def poke(self, context):
        """Check if the input data is ready."""
        logging.info(f"Checking input data for job {self.job_id}")
        return os.path.exists(self.input_path) and len(os.listdir(self.input_path)) > 0
```

### XComs

E2E3D uses XComs for data sharing between tasks:

```python
def extract_features(ti, **kwargs):
    """Extract features from images."""
    job_id = kwargs['job_id']
    # Process job
    result = {
        'feature_count': 1250,
        'matching_pairs': 45,
        'processing_time': 120.5
    }
    # Push result to XCom
    ti.xcom_push(key='feature_extraction_result', value=result)
    return result

def generate_cameras(ti, **kwargs):
    """Generate camera positions."""
    # Pull result from previous task
    feature_result = ti.xcom_pull(
        task_ids='extract_features',
        key='feature_extraction_result'
    )
    # Use the result
    feature_count = feature_result['feature_count']
    # Continue processing
```

## Conclusion

Airflow provides E2E3D with a powerful, flexible workflow orchestration system. By defining reconstruction workflows as DAGs, the system gains reliable execution, comprehensive monitoring, and robust error handling. The integration with other components through the REST API enables seamless job submission and status tracking, while the Airflow web interface offers visibility into the system's operation.

As E2E3D's reconstruction workflows evolve, Airflow's extensibility through custom operators, sensors, and other components ensures that the orchestration layer can adapt to new requirements and use cases. 