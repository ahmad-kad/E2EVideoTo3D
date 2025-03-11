# Artifact Storage and Multi-Purpose Pipeline Structure

This guide outlines strategies for structuring artifact storage in the E2E3D system to support multiple use cases, including 3D reconstruction, computer vision, and neural radiance fields (NeRFs). It also covers how to integrate various ML models to enhance the pipeline.

## Table of Contents

- [Storage Organization](#storage-organization)
- [Branching Pipeline Architecture](#branching-pipeline-architecture)
- [Use Case Implementations](#use-case-implementations)
  - [3D Reconstruction](#3d-reconstruction)
  - [Computer Vision](#computer-vision)
  - [Neural Radiance Fields](#neural-radiance-fields)
- [ML Model Integration](#ml-model-integration)
  - [DinoV2 Integration](#dinov2-integration)
  - [YOLO Integration](#yolo-integration)
  - [LLM Integration](#llm-integration)
- [Practical Implementation Guide](#practical-implementation-guide)

## Storage Organization

### Bucket Structure

The E2E3D system uses MinIO for object storage, organized in a hierarchical structure:

```
s3://
├── raw-videos/
│   ├── <venue_id>/
│   │   ├── <event_id>/
│   │   │   ├── <camera_id>_<timestamp>.mp4
│   │   │   └── metadata/
│   │   │       └── <camera_id>_<timestamp>.json
├── frames/
│   ├── <venue_id>/
│   │   ├── <event_id>/
│   │   │   ├── <camera_id>/
│   │   │   │   ├── <frame_id>.jpg
│   │   │   │   └── metadata/
│   │   │   │       └── extraction_info.json
├── annotations/
│   ├── <venue_id>/
│   │   ├── <event_id>/
│   │   │   ├── <model_type>/
│   │   │   │   ├── <camera_id>/
│   │   │   │   │   ├── <frame_id>.json
│   │   │   │   │   └── summary.json
├── processed-frames/
│   ├── <venue_id>/
│   │   ├── <event_id>/
│   │   │   ├── <process_type>/
│   │   │   │   ├── <camera_id>/
│   │   │   │   │   └── <frame_id>.<ext>
├── features/
│   ├── <venue_id>/
│   │   ├── <event_id>/
│   │   │   ├── <feature_extractor>/
│   │   │   │   ├── <camera_id>/
│   │   │   │   │   └── <frame_id>.pkl
├── models/
│   ├── 3d-reconstruction/
│   │   ├── <venue_id>/
│   │   │   ├── <event_id>/
│   │   │   │   ├── mesh/
│   │   │   │   ├── point-cloud/
│   │   │   │   └── textures/
│   ├── neural-fields/
│   │   ├── <venue_id>/
│   │   │   ├── <event_id>/
│   │   │   │   ├── <model_type>/
│   │   │   │   │   └── <timestamp>/
│   ├── ml-models/
│   │   ├── <model_type>/
│   │   │   ├── <version>/
│   │   │   │   ├── weights/
│   │   │   │   └── config/
├── training-data/
│   ├── <dataset_name>/
│   │   ├── images/
│   │   ├── labels/
│   │   └── splits/
```

### Storage Policies

- **Retention Policy**: Define how long different artifacts should be stored
  - Raw videos: Archived after processing (compressed)
  - Frames: Retained as long as needed for derivatives
  - Processed outputs: Kept based on use case requirements

- **Versioning**: Enable versioning for critical outputs and models
  - Track model versioning with clear naming conventions
  - Maintain version metadata for reproducibility

## Branching Pipeline Architecture

The E2E3D pipeline is designed with a branching architecture to support multiple use cases from the same source data:

```
                      ┌─────────────────┐
                      │                 │
                      │  Raw Videos     │
                      │                 │
                      └───────┬─────────┘
                              │
                              ▼
                      ┌─────────────────┐
                      │                 │
                      │  Frame          │
                      │  Extraction     │
                      │                 │
                      └───────┬─────────┘
                              │
               ┌──────────────┴──────────────┐
               │                             │
               ▼                             ▼
      ┌─────────────────┐           ┌─────────────────┐
      │                 │           │                 │
      │  Feature        │           │  Object         │
      │  Extraction     │           │  Detection      │
      │                 │           │                 │
      └───────┬─────────┘           └───────┬─────────┘
              │                             │
    ┌─────────┴──────────┐        ┌─────────┴──────────┐
    │                    │        │                    │
    ▼                    ▼        ▼                    ▼
┌─────────┐       ┌─────────────┐ ┌─────────┐   ┌─────────────┐
│         │       │             │ │         │   │             │
│  3D     │       │  Neural     │ │  ML     │   │  Object     │
│  Recon- │       │  Radiance   │ │  Train  │   │             │
│  struct │       │  Fields     │ │         │   │             │
│         │       │             │ │         │   │             │
└─────────┘       └─────────────┘ └─────────┘   └─────────────┘
```

### Pipeline Implementation in Airflow

The pipeline branching can be implemented using Airflow DAGs:

```python
# Example DAG structure with branching
with DAG('multi_purpose_pipeline', ...) as dag:
    # Common tasks
    extract_frames = PythonOperator(
        task_id='extract_frames',
        python_callable=extract_frames_function
    )
    
    # Branching operator
    branch_task = BranchPythonOperator(
        task_id='branch_by_purpose',
        python_callable=determine_pipeline_branch
    )
    
    # 3D Reconstruction branch
    feature_extraction = PythonOperator(
        task_id='feature_extraction',
        python_callable=extract_features
    )
    
    reconstruction_task = PythonOperator(
        task_id='run_reconstruction',
        python_callable=run_meshroom
    )
    
    # Computer Vision branch
    object_detection = PythonOperator(
        task_id='object_detection',
        python_callable=run_detection_model
    )
    
    training_prep = PythonOperator(
        task_id='prepare_training_data',
        python_callable=prepare_for_training
    )
    
    # Set up dependencies
    extract_frames >> branch_task
    branch_task >> [feature_extraction, object_detection]
    feature_extraction >> reconstruction_task
    object_detection >> training_prep
```

## Use Case Implementations

### 3D Reconstruction

The 3D reconstruction pipeline requires high-quality frames and precise camera information:

1. **Frame Selection**: Use quality metrics to select the best frames
2. **Feature Extraction**: Extract SIFT/ORB features for matching
3. **Structure from Motion**: Estimate camera positions and sparse point cloud
4. **Multi-View Stereo**: Generate dense point cloud
5. **Meshing**: Create 3D mesh from point cloud
6. **Texturing**: Apply textures from original images

**Integration Points**:
- Use ML models to improve feature matching
- Apply semantic segmentation for background removal
- Use depth estimation models to enhance reconstruction

### Computer Vision

The computer vision pipeline focuses on extracting information and training models:

1. **Data Annotation**: Manual or automated labeling of frames
2. **Model Training**: Train task-specific models (detection, segmentation)
3. **Model Deployment**: Deploy models for inference
4. **Result Aggregation**: Combine results from multiple frames/cameras

**Implementation Example for Object Detection**:
```python
def train_detection_model(venue_id, event_id, model_type="yolov8"):
    # Load training data
    training_data = load_training_frames(venue_id, event_id)
    
    # Set up model configuration
    if model_type == "yolov8":
        model = YOLO('yolov8n.pt')
        
        # Train the model
        results = model.train(
            data=f"configs/{venue_id}_dataset.yaml",
            epochs=100,
            imgsz=640,
            batch=16,
            name=f"{venue_id}_{event_id}_model"
        )
        
        # Save model to MinIO
        save_model_to_storage(
            model_path=results.model_path,
            bucket="models",
            path=f"ml-models/object-detection/yolov8/{venue_id}_{event_id}/weights/"
        )
```

### Neural Radiance Fields

Neural Radiance Fields (NeRFs) create implicit 3D representations from images:

1. **Camera Calibration**: Precise camera parameters needed
2. **Frame Selection**: Choose frames with good coverage
3. **Training**: Train NeRF model on selected frames
4. **Rendering**: Generate novel views from trained model

**Implementation Considerations**:
- Integrate with Nerfstudio or Instant-NGP for efficient training
- Use pre-trained models for faster convergence
- Consider hybrid approaches combining mesh with NeRF

## ML Model Integration

### DinoV2 Integration

DINOv2 can be used for feature extraction and zero-shot classification:

```python
def extract_dino_features(frames_path, output_path):
    """Extract DINOv2 features from frames and save them."""
    
    # Load DINOv2 model
    model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
    model.eval()
    
    # Process frames
    features_dict = {}
    for frame_path in glob.glob(f"{frames_path}/*.jpg"):
        # Load and preprocess image
        image = Image.open(frame_path)
        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        img = transform(image).unsqueeze(0)
        
        # Extract features
        with torch.no_grad():
            features = model(img)
            
        # Save features
        frame_id = os.path.basename(frame_path).split('.')[0]
        features_dict[frame_id] = features.squeeze().cpu().numpy()
    
    # Save all features to disk
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'wb') as f:
        pickle.dump(features_dict, f)
```

### YOLO Integration

YOLO can be integrated for object detection and tracking:

```python
def run_yolo_detection(venue_id, event_id, camera_id, model_version="yolov8x"):
    """Run YOLO object detection on frames and save annotations."""
    
    # Load YOLO model
    model = YOLO(model_version)
    
    # Get frame paths
    frames_path = f"s3://frames/{venue_id}/{event_id}/{camera_id}/"
    output_path = f"s3://annotations/{venue_id}/{event_id}/yolo/{camera_id}/"
    
    # Create output directory
    os.makedirs(output_path, exist_ok=True)
    
    # Process frames
    results = []
    for frame_path in glob.glob(f"{frames_path}/*.jpg"):
        frame_id = os.path.basename(frame_path).split('.')[0]
        
        # Run detection
        detections = model(frame_path)
        
        # Convert to standard format
        annotations = []
        for detection in detections[0].boxes.data:
            x1, y1, x2, y2, confidence, class_id = detection
            annotations.append({
                "bbox": [float(x1), float(y1), float(x2), float(y2)],
                "confidence": float(confidence),
                "class_id": int(class_id),
                "class_name": model.names[int(class_id)]
            })
        
        # Save annotations
        with open(f"{output_path}/{frame_id}.json", 'w') as f:
            json.dump(annotations, f)
            
        results.append({
            "frame_id": frame_id,
            "detections_count": len(annotations)
        })
    
    # Save summary
    with open(f"{output_path}/summary.json", 'w') as f:
        json.dump(results, f)
```

### LLM Integration

LLMs can be used for content analysis and metadata enhancement:

```python
def enhance_metadata_with_llm(venue_id, event_id, llm_model="gpt-4"):
    """Use LLM to analyze and enhance metadata."""
    
    # Load detection results
    detections_path = f"s3://annotations/{venue_id}/{event_id}/yolo/"
    
    # Initialize LLM client
    client = OpenAI()
    
    # Process each camera's annotations
    for camera_dir in glob.glob(f"{detections_path}/*"):
        camera_id = os.path.basename(camera_dir)
        
        # Load summary
        with open(f"{camera_dir}/summary.json", 'r') as f:
            summary = json.load(f)
        
        # Sample some detection frames
        sample_frames = random.sample(summary, min(5, len(summary)))
        
        # Gather detection data
        detections_data = []
        for frame_data in sample_frames:
            with open(f"{camera_dir}/{frame_data['frame_id']}.json", 'r') as f:
                detections_data.append(json.load(f))
        
        # Prepare prompt for LLM
        prompt = f"""
        Analyze these object detections from camera {camera_id} at venue {venue_id}, event {event_id}:
        {json.dumps(detections_data)}
        
        Provide the following analysis:
        1. What kind of scene is this likely to be?
        2. What are the main objects/people detected?
        3. Any notable patterns or relationships?
        4. Suggested tags for this content
        """
        
        # Get LLM response
        response = client.chat.completions.create(
            model=llm_model,
            messages=[{"role": "system", "content": "You analyze object detection data to provide scene understanding."},
                      {"role": "user", "content": prompt}]
        )
        
        # Save enhanced metadata
        with open(f"{camera_dir}/llm_analysis.json", 'w') as f:
            json.dump({
                "analysis": response.choices[0].message.content,
                "model": llm_model,
                "timestamp": datetime.now().isoformat()
            }, f)
```

## Practical Implementation Guide

### Setting Up a New Venue

1. **Create the venue structure** in MinIO:

```bash
mc mb myminio/raw-videos/<venue_id>
mc mb myminio/frames/<venue_id>
mc mb myminio/models/3d-reconstruction/<venue_id>
mc mb myminio/models/neural-fields/<venue_id>
```

2. **Create an Airflow variable** for the venue configuration:

```json
{
  "venue_id": "stadium_01",
  "description": "Main football stadium",
  "cameras": [
    {"id": "cam_01", "position": "north", "type": "fixed"},
    {"id": "cam_02", "position": "south", "type": "fixed"},
    {"id": "cam_03", "position": "drone", "type": "mobile"}
  ],
  "use_cases": ["3d_reconstruction", "object_detection", "nerf"]
}
```

3. **Create an event-specific configuration**:

```json
{
  "event_id": "game_20231015",
  "venue_id": "stadium_01",
  "date": "2023-10-15",
  "description": "Championship game",
  "pipeline_config": {
    "frame_extraction": {
      "fps": 5,
      "quality": 95
    },
    "3d_reconstruction": {
      "enabled": true,
      "method": "meshroom",
      "settings": {"detail_level": "high"}
    },
    "object_detection": {
      "enabled": true,
      "model": "yolov8x",
      "confidence": 0.25
    },
    "nerf": {
      "enabled": false
    }
  }
}
```

### Running the Pipeline for Multiple Use Cases

1. **Upload a video** to the raw-videos bucket:

```bash
mc cp game_footage.mp4 myminio/raw-videos/stadium_01/game_20231015/cam_01_20231015T140000Z.mp4
```

2. **Create and upload metadata**:

```json
{
  "camera_id": "cam_01",
  "timestamp": "2023-10-15T14:00:00Z",
  "duration": 3600,
  "resolution": [3840, 2160],
  "fps": 30,
  "codec": "h264",
  "position": {"lat": 37.7749, "lon": -122.4194, "elevation": 20}
}
```

3. **Trigger the pipeline** in Airflow, selecting the venue, event, and use cases:

```bash
airflow dags trigger multi_purpose_pipeline \
  --conf '{"venue_id": "stadium_01", "event_id": "game_20231015", "use_cases": ["3d_reconstruction", "object_detection"]}'
```

4. **Monitor progress** through the Airflow UI and check generated artifacts in MinIO.

---

By following this structured approach to artifact storage and pipeline branching, you can efficiently manage multiple AI/ML use cases from the same source data while maintaining organization and traceability. 