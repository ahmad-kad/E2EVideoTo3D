import cv2
import os
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

def extract_frames(video_path: str, output_dir: str, max_frames: int = 300) -> List[str]:
    """
    Extract frames from a video file with adaptive sampling.
    
    Args:
        video_path: Path to the input video
        output_dir: Directory to save extracted frames
        max_frames: Maximum number of frames to extract
        
    Returns:
        List of paths to extracted frames
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    # Calculate the step size to get at most max_frames
    step_size = max(1, total_frames // max_frames)
    
    # Calculate frames per second to extract (max 2 FPS)
    target_fps = min(2, fps)
    
    # Calculate frame indices to extract
    frame_indices = list(range(0, total_frames, step_size))
    
    extracted_frames = []
    
    for i, frame_idx in enumerate(frame_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if ret:
            frame_path = os.path.join(output_dir, f"frame_{i:06d}.png")
            cv2.imwrite(frame_path, frame)
            extracted_frames.append(frame_path)
        else:
            logger.warning(f"Failed to extract frame at index {frame_idx}")
    
    cap.release()
    logger.info(f"Extracted {len(extracted_frames)} frames from {video_path}")
    
    return extracted_frames

def calculate_fps(video_path: str) -> float:
    """
    Calculate the optimal FPS for frame extraction (max 2 FPS).
    
    Args:
        video_path: Path to the input video
        
    Returns:
        Target frames per second for extraction
    """
    cap = cv2.VideoCapture(video_path)
    target_fps = min(2, cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    return target_fps 