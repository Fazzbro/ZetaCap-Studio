import numpy as np
from moviepy import TextClip, ImageClip

def ease_out_back(progress):
    """Easing function for organic bounce effect."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * ((progress - 1) ** 3) + c1 * ((progress - 1) ** 2)

def get_spring_scale(t, duration=0.25):
    """Kinetic zoom bounce starting at 75%, overshooting to ~115%, settling at 100%."""
    if t >= duration:
        return 1.0
    p = max(0.0, min(1.0, t / duration))
    return 1.0 - 0.25 * ((1.0 - p) ** 3) + 1.5 * p * ((1.0 - p) ** 2)

def get_entry_tilt(t, duration=0.25, start_angle=-2.8):
    """Rotational tilt overshoot starting around -3 degrees and settling smoothly at 0 degrees."""
    if t >= duration:
        return 0.0
    p = max(0.0, min(1.0, t / duration))
    return start_angle * ((1.0 - p) ** 2)

def apply_wipe_filter(clip, duration=0.3, feather_width=35):
    """Applies a smooth quadratic wipe transition from left to right with horizontal alpha feathering."""
    def fl_filter(get_frame, t):
        frame = get_frame(t)
        progress = min(t / duration, 1.0)
        progress = 1 - (1 - progress) ** 2  # Quadratic ease out
        w = frame.shape[1]
        current_w = int(w * progress)
        new_frame = np.copy(frame)
        if current_w < w:
            feather_start = max(0, current_w - feather_width)
            if feather_start < current_w:
                ramp = np.linspace(1.0, 0.0, current_w - feather_start)
                if new_frame.ndim == 3:
                    for c in range(new_frame.shape[2]):
                        new_frame[:, feather_start:current_w, c] = (new_frame[:, feather_start:current_w, c] * ramp).astype(new_frame.dtype)
                else:
                    new_frame[:, feather_start:current_w] = (new_frame[:, feather_start:current_w] * ramp).astype(new_frame.dtype)
            if new_frame.ndim == 2:
                new_frame[:, current_w:] = 0
            else:
                new_frame[:, current_w:, :] = 0
        return new_frame
    
    new_clip = clip.transform(fl_filter)
    if clip.mask:
        new_clip.mask = clip.mask.transform(fl_filter)
    return new_clip

def make_rise_anim(base_x, base_y, chunk_duration, travel_dist, offset_x=0, offset_y=0):
    """Constructs position callback function for the pop-in rise animation."""
    def anim(t):
        anim_dur = min(0.25, chunk_duration)
        progress = min(t / anim_dur, 1.0)
        eased = ease_out_back(progress) if progress < 1.0 else 1.0
        start_y = base_y + travel_dist
        current_y = start_y - (travel_dist * eased)
        return (base_x + offset_x, current_y + offset_y)
    return anim

