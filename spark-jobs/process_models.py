#!/usr/bin/env python3
"""
Spark job to process reconstructed 3D models data.
This job:
1. Reads model metadata from MinIO
2. Calculates statistics (vertices, faces, complexity)
3. Stores processed data back to MinIO
"""
import os
import json
import tempfile
from datetime import datetime
from urllib.parse import urlparse
import trimesh
import numpy as np

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, FloatType, IntegerType
from pyspark.sql.functions import col, udf, to_json, struct

# Initialize Spark session
spark = SparkSession.builder \
    .appName("3D Model Processing") \
    .getOrCreate()

# MinIO connection parameters
MINIO_HOST = os.environ.get("MINIO_HOST", "minio")
MINIO_PORT = os.environ.get("MINIO_PORT", "9000")
MINIO_ACCESS_KEY = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.environ.get("MINIO_BUCKET", "models")

# Set Hadoop AWS configuration for S3/MinIO access
spark._jsc.hadoopConfiguration().set("fs.s3a.endpoint", f"http://{MINIO_HOST}:{MINIO_PORT}")
spark._jsc.hadoopConfiguration().set("fs.s3a.access.key", MINIO_ACCESS_KEY)
spark._jsc.hadoopConfiguration().set("fs.s3a.secret.key", MINIO_SECRET_KEY)
spark._jsc.hadoopConfiguration().set("fs.s3a.path.style.access", "true")
spark._jsc.hadoopConfiguration().set("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")

# Schema for model metadata
model_schema = StructType([
    StructField("model_id", StringType(), True),
    StructField("image_set", StringType(), True),
    StructField("reconstruction_date", StringType(), True),
    StructField("file_path", StringType(), True)
])

def download_from_minio(minio_path):
    """Download file from MinIO to local temp file"""
    import boto3
    from botocore.client import Config
    
    s3_client = boto3.client(
        's3',
        endpoint_url=f'http://{MINIO_HOST}:{MINIO_PORT}',
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    parsed_url = urlparse(minio_path)
    bucket_name = parsed_url.netloc
    object_key = parsed_url.path.lstrip('/')
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.obj')
    temp_file.close()
    
    s3_client.download_file(bucket_name, object_key, temp_file.name)
    return temp_file.name

def upload_to_minio(local_path, minio_path):
    """Upload file to MinIO"""
    import boto3
    from botocore.client import Config
    
    s3_client = boto3.client(
        's3',
        endpoint_url=f'http://{MINIO_HOST}:{MINIO_PORT}',
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    parsed_url = urlparse(minio_path)
    bucket_name = parsed_url.netloc
    object_key = parsed_url.path.lstrip('/')
    
    s3_client.upload_file(local_path, bucket_name, object_key)
    return minio_path

def analyze_mesh(minio_path):
    """Analyze a 3D mesh and extract stats"""
    try:
        # Download the mesh file
        local_path = download_from_minio(minio_path)
        
        # Load the mesh
        mesh = trimesh.load(local_path)
        
        # Calculate basic stats
        volume = float(mesh.volume) if hasattr(mesh, 'volume') else 0.0
        surface_area = float(mesh.area) if hasattr(mesh, 'area') else 0.0
        
        # Get number of vertices and faces
        vertices = int(len(mesh.vertices))
        faces = int(len(mesh.faces))
        
        # Calculate bounding box dimensions
        if hasattr(mesh, 'bounds'):
            bounds = mesh.bounds
            dimensions = bounds[1] - bounds[0]
            width = float(dimensions[0])
            height = float(dimensions[1])
            depth = float(dimensions[2])
        else:
            width, height, depth = 0.0, 0.0, 0.0
        
        # Calculate complexity metrics
        complexity = float(faces) / 1000  # Faces per thousand
        
        # Calculate mesh density (faces per unit volume)
        density = float(faces) / volume if volume > 0 else 0.0
        
        # Clean up
        os.unlink(local_path)
        
        return {
            "vertices": vertices,
            "faces": faces,
            "volume": volume,
            "surface_area": surface_area,
            "width": width,
            "height": height,
            "depth": depth,
            "complexity": complexity,
            "density": density,
            "processed_date": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "processed_date": datetime.now().isoformat()
        }

def process_model_batch(batch_df):
    """Process a batch of model files"""
    # Convert the analyze_mesh function to a UDF
    analyze_mesh_udf = udf(analyze_mesh, StringType())
    
    # Apply the UDF to each row
    processed_df = batch_df.withColumn("analysis_json", 
                                      analyze_mesh_udf(col("file_path")))
    
    # Write results to MinIO as JSON
    for row in processed_df.collect():
        model_id = row["model_id"]
        image_set = row["image_set"]
        
        # Write analysis to temporary JSON file
        analysis_data = json.loads(row["analysis_json"])
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        with open(temp_file.name, 'w') as f:
            json.dump(analysis_data, f)
        
        # Upload to MinIO
        minio_path = f"s3a://{MINIO_BUCKET}/processed/{image_set}/{model_id}_analysis.json"
        upload_to_minio(temp_file.name, minio_path)
        
        # Clean up
        os.unlink(temp_file.name)
    
    return processed_df

def main():
    # Create a dummy DataFrame with model metadata
    # In a real setup, this would come from a database or MinIO listing
    data = [
        ("model001", "CognacStJacquesDoor", datetime.now().isoformat(), 
         f"s3a://{MINIO_BUCKET}/models/CognacStJacquesDoor/mesh/reconstructed_mesh.obj"),
        ("model002", "FrameSequence", datetime.now().isoformat(), 
         f"s3a://{MINIO_BUCKET}/models/FrameSequence/mesh/reconstructed_mesh.obj")
    ]
    
    models_df = spark.createDataFrame(data, model_schema)
    
    # Process models
    processed_df = process_model_batch(models_df)
    
    # Show results
    processed_df.show(truncate=False)
    
    print("Model processing completed successfully")

if __name__ == "__main__":
    main() 