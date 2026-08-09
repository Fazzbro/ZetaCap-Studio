import cv2
import mediapipe as mp
import numpy as np
import os
from moviepy.editor import VideoFileClip, AudioFileClip

# ==========================================
# CONFIGURATION
# ==========================================
INPUT_VIDEO = "30713.mp4"
OUTPUT_VIDEO = "30713_reframed.mp4"

# The target aspect ratio for shorts/reels is 9:16
TARGET_ASPECT = 9 / 16

# EMA Smoothing Factor (alpha). 
# Lower = Smoother but more delayed tracking (e.g. 0.05).
# Higher = Faster tracking but more robotic/jittery (e.g. 0.30).
EMA_ALPHA = 0.12 

# Optional base zoom to ensure we have a margin. 
# 1.0 means no zoom, 1.2 means zoom in 20%.
BASE_ZOOM = 1.15 

# ==========================================
# INITIALIZATION
# ==========================================
mp_face_detection = mp.solutions.face_detection
face_detection = mp_face_detection.FaceDetection(
    model_selection=1, # 0 for short-range, 1 for full-range
    min_detection_confidence=0.5
)

def process_video():
    if not os.path.exists(INPUT_VIDEO):
        print(f"Error: {INPUT_VIDEO} not found.")
        return

    # Open video to read properties
    cap = cv2.VideoCapture(INPUT_VIDEO)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Calculate optimal crop window size (target width and height)
    # We want 9:16 aspect ratio. Usually we constrain by the height of the original video.
    crop_h = int(height / BASE_ZOOM)
    crop_w = int(crop_h * TARGET_ASPECT)
    
    # If the calculated crop_w is wider than the video, constrain by width instead
    if crop_w > int(width / BASE_ZOOM):
        crop_w = int(width / BASE_ZOOM)
        crop_h = int(crop_w / TARGET_ASPECT)
        
    print(f"Original Video: {width}x{height} | Crop Window: {crop_w}x{crop_h}")

    # Set up Video Writer
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    temp_output = "temp_no_audio.mp4"
    out = cv2.VideoWriter(temp_output, fourcc, fps, (crop_w, crop_h))

    # State variables for EMA
    prev_smooth_x = None
    prev_smooth_y = None

    frame_count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        
        # Convert the BGR image to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_detection.process(rgb_frame)

        # 1. Target Identification
        if results.detections:
            # Get the first face detected
            detection = results.detections[0]
            bboxC = detection.location_data.relative_bounding_box
            
            # 2. Anchor Point (Center of the face bounding box)
            target_x = int((bboxC.xmin + bboxC.width / 2) * width)
            target_y = int((bboxC.ymin + bboxC.height / 2) * height)
        else:
            # 6. Fallback Logic: If no face, keep the target where the camera currently is
            if prev_smooth_x is not None:
                target_x = prev_smooth_x
                target_y = prev_smooth_y
            else:
                target_x = width // 2
                target_y = height // 2

        # 3. Cinematic Smoothing (EMA)
        if prev_smooth_x is None:
            # Initialize EMA on the first frame
            smooth_x = target_x
            smooth_y = target_y
        else:
            # Apply EMA formula
            smooth_x = (EMA_ALPHA * target_x) + ((1 - EMA_ALPHA) * prev_smooth_x)
            smooth_y = (EMA_ALPHA * target_y) + ((1 - EMA_ALPHA) * prev_smooth_y)
            
        prev_smooth_x = smooth_x
        prev_smooth_y = smooth_y

        # 4. Dynamic Cropping - Calculate top-left coordinates of the crop window
        ideal_x1 = int(smooth_x - (crop_w / 2))
        ideal_y1 = int(smooth_y - (crop_h / 2))

        # 5. Boundary Clamping
        # Prevent the crop window from going below 0 or above (width - crop_w)
        clamped_x1 = max(0, min(ideal_x1, width - crop_w))
        clamped_y1 = max(0, min(ideal_y1, height - crop_h))
        
        clamped_x2 = clamped_x1 + crop_w
        clamped_y2 = clamped_y1 + crop_h

        # 7. Output - Slice the numpy array
        cropped_frame = frame[clamped_y1:clamped_y2, clamped_x1:clamped_x2]

        out.write(cropped_frame)
        
        if frame_count % 30 == 0:
            print(f"Processed {frame_count}/{total_frames} frames...")

    # Cleanup
    cap.release()
    out.release()
    face_detection.close()
    
    print("Video processing complete. Merging audio using moviepy...")
    
    # Merge audio back in
    try:
        original_clip = VideoFileClip(INPUT_VIDEO)
        processed_clip = VideoFileClip(temp_output)
        
        if original_clip.audio is not None:
            final_clip = processed_clip.set_audio(original_clip.audio)
            final_clip.write_videofile(OUTPUT_VIDEO, codec="libx264", audio_codec="aac", logger=None)
        else:
            processed_clip.write_videofile(OUTPUT_VIDEO, codec="libx264", logger=None)
            
        original_clip.close()
        processed_clip.close()
        
        # Remove temporary video
        if os.path.exists(temp_output):
            os.remove(temp_output)
            
        print(f"Success! Final video saved to {OUTPUT_VIDEO}")
    except Exception as e:
        print(f"Error merging audio: {e}. The video without audio is saved as {temp_output}")

if __name__ == "__main__":
    process_video()
