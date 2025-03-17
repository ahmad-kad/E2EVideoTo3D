from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
import os
import json
import random

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 3, 17),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Create a DAG instance
dag = DAG(
    'etl_pipeline',
    default_args=default_args,
    description='An ETL pipeline for data processing',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

# Define the data directories
data_dir = os.path.join(os.environ.get('AIRFLOW_HOME', '.'), 'data')
raw_data_dir = os.path.join(data_dir, 'raw')
processed_data_dir = os.path.join(data_dir, 'processed')

# Create directories if they don't exist
for directory in [data_dir, raw_data_dir, processed_data_dir]:
    os.makedirs(directory, exist_ok=True)

# Define Python functions for our ETL tasks
def extract_data(**kwargs):
    """Generate sample data and save it to a JSON file."""
    ti = kwargs['ti']
    
    # Generate sample data (10 records of random numbers)
    data = {
        'records': [
            {
                'id': i,
                'value': random.randint(1, 100),
                'timestamp': datetime.now().isoformat()
            }
            for i in range(1, 11)
        ]
    }
    
    # Save to a file in the raw data directory
    output_file = os.path.join(raw_data_dir, f'data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Extracted data saved to {output_file}")
    
    # Pass the file path to the next task
    ti.xcom_push(key='data_file', value=output_file)
    
    return output_file

def transform_data(**kwargs):
    """Transform the data by calculating some statistics."""
    ti = kwargs['ti']
    
    # Get the file path from the previous task
    input_file = ti.xcom_pull(task_ids='extract_data', key='data_file')
    
    # Load the data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Transform: Calculate sum, average, min, max
    values = [record['value'] for record in data['records']]
    stats = {
        'count': len(values),
        'sum': sum(values),
        'average': sum(values) / len(values) if values else 0,
        'min': min(values) if values else None,
        'max': max(values) if values else None
    }
    
    # Add stats to the data
    data['statistics'] = stats
    
    # Save to a file in the processed data directory
    output_file = os.path.join(processed_data_dir, f'processed_{os.path.basename(input_file)}')
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Transformed data saved to {output_file}")
    
    # Pass the file path to the next task
    ti.xcom_push(key='processed_file', value=output_file)
    
    return output_file

def load_data(**kwargs):
    """Load data into a target system (simulated here)."""
    ti = kwargs['ti']
    
    # Get the file path from the previous task
    processed_file = ti.xcom_pull(task_ids='transform_data', key='processed_file')
    
    # Load the processed data
    with open(processed_file, 'r') as f:
        data = json.load(f)
    
    # Simulate loading data into a target system by printing the stats
    print("Loading data into target system...")
    print(f"Statistics: {json.dumps(data['statistics'], indent=2)}")
    print("Data successfully loaded!")
    
    return "Data loaded successfully"

# Task 1: Extract data
extract_task = PythonOperator(
    task_id='extract_data',
    python_callable=extract_data,
    provide_context=True,
    dag=dag,
)

# Task 2: Transform data
transform_task = PythonOperator(
    task_id='transform_data',
    python_callable=transform_data,
    provide_context=True,
    dag=dag,
)

# Task 3: Load data
load_task = PythonOperator(
    task_id='load_data',
    python_callable=load_data,
    provide_context=True,
    dag=dag,
)

# Task 4: Cleanup (delete raw files older than 7 days)
cleanup_task = BashOperator(
    task_id='cleanup_old_files',
    bash_command=f'find {raw_data_dir} -name "*.json" -type f -mtime +7 -delete || true',
    dag=dag,
)

# Set task dependencies
extract_task >> transform_task >> load_task >> cleanup_task 