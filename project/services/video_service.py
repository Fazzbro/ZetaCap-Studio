import cv2
import math
import os
import numpy as np
from moviepy import AudioFileClip
from project.core.config import config

def detect_face_centers_for_intervals(video_path, intervals, model_choice, canvas_w, canvas_h):
    """
    Scans representative frames for each caption block/interval using YuNet or Haar Cascade from D:\\ai_models.
    Returns list of intervals enriched with 'face_cx', 'face_cy', and 'has_face'.
    """
    if not os.path.exists(video_path):
        return intervals

    detector_type = "yunet" if "YuNet" in str(model_choice) and os.path.exists(config.YUNET_MODEL_PATH) else "haar"
    yunet_detector = None
    haar_cascade = None

    if detector_type == "yunet":
        try:
            yunet_detector = cv2.FaceDetectorYN.create(
                model=config.YUNET_MODEL_PATH,
                config="",
                input_size=(canvas_w, canvas_h),
                score_threshold=0.6,
                nms_threshold=0.3,
                top_k=5000
            )
        except Exception as e:
            print(f"[Warning] YuNet initialization failed ({e}). Falling back to Haar Cascade...", flush=True)
            detector_type = "haar"

    if detector_type == "haar":
        if os.path.exists(config.HAAR_MODEL_PATH):
            haar_cascade = cv2.CascadeClassifier(config.HAAR_MODEL_PATH)
        else:
            print(f"[Warning] Haar cascade model not found at {config.HAAR_MODEL_PATH}. Using center fallback.", flush=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return intervals

    default_cx = canvas_w / 2.0
    default_cy = canvas_h / 2.0
    last_cx, last_cy = default_cx, default_cy

    for j, interval in enumerate(intervals):
        t_start = interval["start"]
        t_end = interval["end"]
        t_sample = (t_start + t_end) / 2.0

        cap.set(cv2.CAP_PROP_POS_MSEC, t_sample * 1000.0)
        ret, frame = cap.read()
        if not ret or frame is None:
            interval["face_cx"] = last_cx
            interval["face_cy"] = last_cy
            interval["has_face"] = False
            continue

        fh, fw = frame.shape[:2]
        if (fw, fh) != (canvas_w, canvas_h) and yunet_detector is not None:
            yunet_detector.setInputSize((fw, fh))

        face_found = False
        cx, cy = last_cx, last_cy

        if detector_type == "yunet" and yunet_detector is not None:
            try:
                _, faces = yunet_detector.detect(frame)
                if faces is not None and len(faces) > 0:
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = best_face[0], best_face[1], best_face[2], best_face[3]
                    scale_x = canvas_w / float(fw)
                    scale_y = canvas_h / float(fh)
                    cx = (x + w / 2.0) * scale_x
                    cy = (y + h / 2.0) * scale_y
                    face_found = True
            except Exception:
                pass

        if not face_found and haar_cascade is not None:
            try:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = haar_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                if len(faces) > 0:
                    best_face = max(faces, key=lambda f: f[2] * f[3])
                    x, y, w, h = best_face[0], best_face[1], best_face[2], best_face[3]
                    scale_x = canvas_w / float(fw)
                    scale_y = canvas_h / float(fh)
                    cx = (x + w / 2.0) * scale_x
                    cy = (y + h / 2.0) * scale_y
                    face_found = True
            except Exception:
                pass

        if face_found:
            last_cx, last_cy = cx, cy

        interval["face_cx"] = last_cx
        interval["face_cy"] = last_cy
        interval["has_face"] = face_found

    cap.release()
    return intervals


def apply_auto_zoom_to_clip(clip, intervals, zoom_factor, zoom_frequency, zoom_transition_style, canvas_w, canvas_h, min_cooldown=6.0, zoom_hold=4.0):
    """
    Applies occasional auto-zoom (punch-in/out) centered on detected faces using smooth transitions or instant cuts.
    Includes Intelligent Cadence (time-based cooldown & hold duration) and Keyword/Emphasis trigger modes.
    """
    if clip is None or not intervals or float(zoom_factor) <= 1.001:
        return clip

    cooldown_sec = float(min_cooldown) if min_cooldown is not None else 6.0
    hold_sec = float(zoom_hold) if zoom_hold is not None else 4.0

    if "Intelligent Cadence" in str(zoom_frequency) or "Time-Based" in str(zoom_frequency):
        current_state = False
        state_change_time = 0.0
        
        for j, interval in enumerate(intervals):
            t_start = interval["start"]
            t_end = interval["end"]
            
            if not current_state:
                if t_start >= state_change_time + cooldown_sec:
                    current_state = True
                    state_change_time = t_start
            else:
                if t_start >= state_change_time + hold_sec:
                    current_state = False
                    state_change_time = t_start
            interval["is_zoomed"] = current_state

    elif "Keyword" in str(zoom_frequency) or "Emphasis" in str(zoom_frequency):
        impact_words = {"money", "secret", "important", "listen", "look", "here", "why", "how", "best", "now", "never", "always"}
        for j, interval in enumerate(intervals):
            txt = interval.get("text", "").lower()
            has_punc = ("!" in txt or "?" in txt)
            has_word = any(iw in txt.split() for iw in impact_words)
            interval["is_zoomed"] = (has_punc or has_word)
    else:
        for j, interval in enumerate(intervals):
            chunk_dur = interval["end"] - interval["start"]
            if "Every 2nd Caption Block" in str(zoom_frequency):
                interval["is_zoomed"] = (j % 2 == 1)
            elif "Every 3rd Caption Block" in str(zoom_frequency):
                interval["is_zoomed"] = (j % 3 == 1)
            elif "Every Caption Block" in str(zoom_frequency):
                interval["is_zoomed"] = True
            elif "Only on Long Chunks" in str(zoom_frequency):
                interval["is_zoomed"] = (chunk_dur >= 2.0)
            else:
                interval["is_zoomed"] = (j % 2 == 1)

    # Pass to lock camera center across each continuous zoom period so it NEVER shifts or jitters mid-zoom!
    idx = 0
    while idx < len(intervals):
        if intervals[idx].get("is_zoomed", False):
            group_end = idx
            while group_end < len(intervals) and intervals[group_end].get("is_zoomed", False):
                group_end += 1
            group_slice = intervals[idx:group_end]
            avg_cx = sum(float(inter.get("face_cx", canvas_w / 2.0)) for inter in group_slice) / len(group_slice)
            avg_cy = sum(float(inter.get("face_cy", canvas_h / 2.0)) for inter in group_slice) / len(group_slice)
            for inter in group_slice:
                inter["locked_face_cx"] = avg_cx
                inter["locked_face_cy"] = avg_cy
            idx = group_end
        else:
            intervals[idx]["locked_face_cx"] = float(canvas_w / 2.0)
            intervals[idx]["locked_face_cy"] = float(canvas_h / 2.0)
            idx += 1

    # Build transition events table across chunk boundaries for ultra-smooth S-Curve animations!
    if "Lush S-Curve" in str(zoom_transition_style) or "Ease-In-Out" in str(zoom_transition_style) or "Smooth Cinematic" in str(zoom_transition_style):
        trans_dur = 0.60
        def ease_curve(x):
            # Quintic Smootherstep S-Curve: zero velocity AND zero acceleration at start/end!
            return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)
    elif "Standard Cinematic" in str(zoom_transition_style) or "0.35s" in str(zoom_transition_style):
        trans_dur = 0.35
        def ease_curve(x):
            return 0.5 * (1.0 - math.cos(math.pi * x))
    elif "Fast Snappy" in str(zoom_transition_style) or "0.20s" in str(zoom_transition_style):
        trans_dur = 0.20
        def ease_curve(x):
            return 1.0 - (1.0 - x) ** 3
    else:
        trans_dur = 0.0
        def ease_curve(x): return 1.0

    zoom_transitions = []
    if trans_dur > 0.0:
        for j in range(1, len(intervals)):
            prev_inter = intervals[j - 1]
            cur_inter = intervals[j]
            prev_zoomed = prev_inter.get("is_zoomed", False)
            cur_zoomed = cur_inter.get("is_zoomed", False)
            
            if prev_zoomed != cur_zoomed:
                t_event = cur_inter["start"]
                if cur_zoomed:
                    # Zoom-In Transition: Wide -> Zoomed
                    from_scale = 1.0
                    from_cx = float(canvas_w / 2.0)
                    from_cy = float(canvas_h / 2.0)
                    to_scale = float(zoom_factor)
                    to_cx = float(cur_inter.get("locked_face_cx", canvas_w / 2.0))
                    to_cy = float(cur_inter.get("locked_face_cy", canvas_h / 2.0))
                else:
                    # Zoom-Out Transition: Zoomed -> Wide
                    from_scale = float(zoom_factor)
                    from_cx = float(prev_inter.get("locked_face_cx", canvas_w / 2.0))
                    from_cy = float(prev_inter.get("locked_face_cy", canvas_h / 2.0))
                    to_scale = 1.0
                    to_cx = float(canvas_w / 2.0)
                    to_cy = float(canvas_h / 2.0)
                    
                zoom_transitions.append({
                    "t_start": t_event,
                    "t_end": t_event + trans_dur,
                    "from_scale": from_scale,
                    "to_scale": to_scale,
                    "from_cx": from_cx,
                    "to_cx": to_cx,
                    "from_cy": from_cy,
                    "to_cy": to_cy
                })

    def fl(get_frame, t):
        frame = get_frame(t)
        if frame is None:
            return frame

        # Check if t falls inside any active smooth S-Curve transition
        active_trans = None
        if trans_dur > 0.0:
            for trans in zoom_transitions:
                if trans["t_start"] <= t < trans["t_end"]:
                    active_trans = trans
                    break

        if active_trans is not None:
            raw_x = (t - active_trans["t_start"]) / (active_trans["t_end"] - active_trans["t_start"])
            alpha = ease_curve(max(0.0, min(1.0, raw_x)))
            current_scale = active_trans["from_scale"] + (active_trans["to_scale"] - active_trans["from_scale"]) * alpha
            current_cx = active_trans["from_cx"] + (active_trans["to_cx"] - active_trans["from_cx"]) * alpha
            current_cy = active_trans["from_cy"] + (active_trans["to_cy"] - active_trans["from_cy"]) * alpha
        else:
            active_idx = -1
            for idx, inter in enumerate(intervals):
                if inter["start"] <= t <= inter["end"]:
                    active_idx = idx
                    break
            if active_idx == -1:
                for idx, inter in enumerate(intervals):
                    if t < inter["start"]:
                        active_idx = idx
                        break
                if active_idx == -1:
                    active_idx = len(intervals) - 1

            cur_inter = intervals[active_idx]
            is_zoomed = cur_inter.get("is_zoomed", False)
            current_scale = float(zoom_factor) if is_zoomed else 1.0
            current_cx = float(cur_inter.get("locked_face_cx", canvas_w / 2.0)) if is_zoomed else float(canvas_w / 2.0)
            current_cy = float(cur_inter.get("locked_face_cy", canvas_h / 2.0)) if is_zoomed else float(canvas_h / 2.0)

        if current_scale <= 1.001:
            return frame

        fh, fw = frame.shape[:2]
        crop_w = int(fw / current_scale)
        crop_h = int(fh / current_scale)

        x1 = int(current_cx * (fw / float(canvas_w)) - crop_w / 2.0)
        y1 = int(current_cy * (fh / float(canvas_h)) - crop_h / 2.0)

        x1 = max(0, min(x1, fw - crop_w))
        y1 = max(0, min(y1, fh - crop_h))
        x2 = x1 + crop_w
        y2 = y1 + crop_h

        cropped = frame[y1:y2, x1:x2]
        zoomed = cv2.resize(cropped, (fw, fh), interpolation=cv2.INTER_LINEAR)
        return zoomed

    return clip.transform(fl)

def resolve_and_load_sfx_clip(sfx_preset, sfx_upload, volume=0.30):
    """Safely resolves the SFX preset or upload path, sanitizing chapters if necessary to avoid MoviePy IndexError."""
    from ..core.config import get_bundled_path
    sfx_path = None
    if sfx_upload and os.path.exists(str(sfx_upload)):
        sfx_path = str(sfx_upload)
    elif str(sfx_preset) != "None":
        sfx_path = None
        if "Mixkit Modern Technology" in str(sfx_preset):
            sfx_path = get_bundled_path(os.path.join("assets", "mixkit-modern-technology-select-3124.wav"), r"d:\Python_Projects\captions\project\assets\mixkit-modern-technology-select-3124.wav")
        elif "Motion Design AfterEffects Pop" in str(sfx_preset):
            sfx_path = get_bundled_path(os.path.join("assets", "hi-sfx-aftereffects-videoediting-motiondesign-motiongraphi_49nxh1eV (1).mp3"), r"d:\Python_Projects\captions\project\assets\hi-sfx-aftereffects-videoediting-motiondesign-motiongraphi_49nxh1eV (1).mp3")
        elif "UI Caption Accent" in str(sfx_preset):
            sfx_path = get_bundled_path(os.path.join("assets", "ui cap.mp3"), r"d:\Python_Projects\captions\project\assets\ui cap.mp3")
    else:
        return None

    if not sfx_path or not os.path.exists(sfx_path):
        return None

    try:
        clip = AudioFileClip(sfx_path)
        if hasattr(clip, "with_volume_scaled"):
            return clip.with_volume_scaled(volume)
        elif hasattr(clip, "volumex"):
            return clip.volumex(volume)
        return clip
    except Exception as e:
        clean_path = sfx_path + ".clean.wav"
        if not os.path.exists(clean_path):
            import subprocess
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
            subprocess.run(["ffmpeg", "-y", "-i", sfx_path, "-map_metadata", "-1", "-map_chapters", "-1", clean_path], capture_output=True, stdin=subprocess.DEVNULL, creationflags=creationflags)
        if os.path.exists(clean_path):
            try:
                clip = AudioFileClip(clean_path)
                if hasattr(clip, "with_volume_scaled"):
                    return clip.with_volume_scaled(volume)
                elif hasattr(clip, "volumex"):
                    return clip.volumex(volume)
                return clip
            except Exception as e2:
                print(f"[AI Studio] Warning: Could not load cleaned SFX clip '{clean_path}': {e2}", flush=True)
                return None
        print(f"[AI Studio] Warning: Could not load SFX clip '{sfx_path}': {e}", flush=True)
        return None


# --- Phase 12: AI Rotoscope / Text-Behind-Speaker Helper ---
_RVM_MODEL = None

def get_rvm_mask(frame_rgb, rec_states=None, downsample_ratio=0.25):
    """
    Runs RobustVideoMatting on a single RGB frame (H, W, 3) using PyTorch CUDA/CPU.
    Returns:
        fgr: Foreground RGB numpy array (H, W, 3) float32 (0..255)
        pha: Alpha mask numpy array (H, W, 1) float32 (0..1)
        new_rec_states: list of 4 recurrent state tensors
    """
    global _RVM_MODEL
    import torch
    import numpy as np

    if _RVM_MODEL is None:
        print("[AI Studio] Loading RobustVideoMatting (MobileNetV3 ~14.8 MB) model...", flush=True)
        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            model = torch.hub.load("PeterL1n/RobustVideoMatting", "mobilenetv3", trust_repo=True)
            _RVM_MODEL = model.to(device).eval()
            print(f"[AI Studio] RobustVideoMatting successfully loaded to {device}!", flush=True)
        except Exception as e:
            print(f"[AI Studio] Error loading RVM model: {e}", flush=True)
            return None, None, rec_states

    if rec_states is None:
        rec_states = [None] * 4

    device = next(_RVM_MODEL.parameters()).device
    # Convert numpy frame (H, W, 3) uint8 to torch tensor (1, 3, H, W) float32 0..1
    src = torch.from_numpy(frame_rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
    if device.type == "cuda":
        src = src.to(device, non_blocking=True)

    with torch.no_grad():
        fgr_t, pha_t, *new_rec_states = _RVM_MODEL(src, *rec_states, downsample_ratio=downsample_ratio)

    # Convert back to numpy arrays
    pha = pha_t[0].permute(1, 2, 0).cpu().numpy() # (H, W, 1) float32 0..1
    fgr = (fgr_t[0].permute(1, 2, 0).cpu().numpy() * 255.0) # (H, W, 3) float32 0..255

    return fgr, pha, new_rec_states

