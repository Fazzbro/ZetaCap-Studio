import os
import cv2
import numpy as np
from PIL import Image

def apply_color_grade(clip, style, custom_lut_path=""):
    """
    Applies a 3D LUT (.cube file) color grade to a MoviePy VideoClip using pillow-lut.
    """
    if style == "None" or not style:
        return clip
        
    print(f"[AI Studio] Applying True 3D LUT Color Grade: {style}...", flush=True)
    
    lut_file = None
    
    if style == "Custom Upload (.cube)":
        if os.path.exists(custom_lut_path) and custom_lut_path.lower().endswith(".cube"):
            lut_file = custom_lut_path
        else:
            print(f"[Warning] Custom LUT file not found or invalid: {custom_lut_path}", flush=True)
            return clip
    else:
        # Prebuilt presets stored in assets/luts
        from project.core.config import get_bundled_path
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        fallback_dir = os.path.join(base_dir, "assets", "luts")
        
        if style == "Cinematic Teal & Orange":
            rel_path = os.path.join("assets", "luts", "Cinematic_Teal_Orange.cube")
            fallback = os.path.join(fallback_dir, "Cinematic_Teal_Orange.cube")
        elif style == "Vibrant Pop":
            rel_path = os.path.join("assets", "luts", "Vibrant_Pop.cube")
            fallback = os.path.join(fallback_dir, "Vibrant_Pop.cube")
        elif style == "Moody B&W":
            rel_path = os.path.join("assets", "luts", "Moody_BW.cube")
            fallback = os.path.join(fallback_dir, "Moody_BW.cube")
            
        lut_file = get_bundled_path(rel_path, fallback)
            
        if not os.path.exists(lut_file):
            print(f"[Warning] Built-in LUT file missing: {lut_file}", flush=True)
            return clip
            
    try:
        from pillow_lut import load_cube_file
        # Load the LUT into memory
        lut = load_cube_file(lut_file)
    except ImportError:
        print("[Warning] pillow-lut is not installed. Please run 'pip install pillow-lut'", flush=True)
        return clip
    except Exception as e:
        print(f"[Warning] Failed to load LUT file {lut_file}: {e}", flush=True)
        return clip
        
    def lut_filter(frame):
        # MoviePy frames can sometimes come in as float or int32. Force to uint8.
        if frame.dtype != np.uint8:
            frame = frame.astype(np.uint8)
            
        # Convert OpenCV/NumPy frame to Pillow Image
        img = Image.fromarray(frame)
        
        # Apply the 3D LUT (Extremely fast C-backend operation)
        graded_img = img.filter(lut)
        
        # Convert back to NumPy array
        return np.array(graded_img)
        
    return clip.image_transform(lut_filter)
