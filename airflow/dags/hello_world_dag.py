from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

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
    'hello_world',
    default_args=default_args,
    description='A simple hello world DAG',
    schedule_interval=timedelta(days=1),
    catchup=False,
)

# Define a Python function that will be used as a task
def print_hello():
    return 'Hello World from Python!'

# Task 1: Run a Bash command
t1 = BashOperator(
    task_id='hello_from_bash',
    bash_command='echo "Hello World from Bash!"',
    dag=dag,
)

# Task 2: Run a Python function
t2 = PythonOperator(
    task_id='hello_from_python',
    python_callable=print_hello,
    dag=dag,
)

# Set task dependencies
t1 >> t2  # t1 runs before t2 