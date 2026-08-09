import subprocess
import re
import os
import imageio_ffmpeg
from moviepy import VideoFileClip

def get_volume_segments(filepath: str, noise_db: int = -35, min_dur: float = 0.5):
    """
    Uses FFmpeg's silencedetect to find all periods of silence in the video.
    Returns a list of 'sound' segments (start, end) where the audio is ACTIVE.
    """
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-i", filepath, 
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}", 
        "-f", "null", "-"
    ]
    # Hide the terminal window on Windows
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NO_WINDOW
        
    res = subprocess.run(cmd, capture_output=True, text=True, creationflags=creationflags)
    
    silences = []
    for line in res.stderr.splitlines():
        if "silence_start" in line:
            match = re.search(r"silence_start:\s+([\d\.]+)", line)
            if match:
                silences.append({"start": float(match.group(1)), "end": None})
        elif "silence_end" in line:
            match = re.search(r"silence_end:\s+([\d\.]+)", line)
            if match and silences and silences[-1]["end"] is None:
                silences[-1]["end"] = float(match.group(1))
                
    # Invert the silences to get sound segments
    try:
        with VideoFileClip(filepath) as c:
            dur = c.duration
    except Exception:
        dur = 9999.0 # Fallback
        
    sound_segments = []
    current_time = 0.0
    
    for s in silences:
        if s["end"] is None: 
            continue # Skip incomplete parses
        
        if s["start"] > current_time:
            # There is sound between current_time and the start of this silence!
            sound_segments.append((current_time, s["start"]))
            
        current_time = s["end"]
        
    if current_time < dur:
        sound_segments.append((current_time, dur))
        
    return sound_segments

def get_whisper_segments(filepath: str, padding: float = 0.3):
    """
    Uses Whisper AI to detect exact timestamps of spoken words.
    Groups words that are close together into segments.
    Returns a list of active sound segments (start, end).
    """
    import whisper_timestamped as whisper
    from ..core.config import config
    
    # Extract audio first
    import uuid
    temp_audio = os.path.join(config.OUTPUT_DIR, f"temp_silence_audio_{uuid.uuid4().hex[:8]}.wav")
    
    try:
        with VideoFileClip(filepath) as video:
            if video.audio:
                video.audio.write_audiofile(temp_audio, logger=None)
            else:
                return [(0.0, video.duration)] # No audio, return whole video
                
        # Load model (tiny is fast enough for silence detection)
        model = whisper.load_model("tiny", device="cpu", download_root=config.WHISPER_MODEL_DIR)
        result = whisper.transcribe(model, temp_audio, language="en") # Language doesn't matter for VAD
        
        # Parse words
        words = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words.append(word)
                
        if not words:
            return [] # Entirely silent
            
        # Group words into contiguous segments if they are close together
        segments = []
        current_seg_start = max(0.0, words[0]["start"] - padding)
        current_seg_end = words[0]["end"] + padding
        
        for i in range(1, len(words)):
            w = words[i]
            w_start = w["start"]
            w_end = w["end"]
            
            # If gap between words is less than 0.8 seconds, keep them in the same segment
            if (w_start - padding) - current_seg_end < 0.8:
                current_seg_end = max(current_seg_end, w_end + padding)
            else:
                segments.append((current_seg_start, current_seg_end))
                current_seg_start = max(0.0, w_start - padding)
                current_seg_end = w_end + padding
                
        segments.append((current_seg_start, current_seg_end))
        
        return segments
        
    finally:
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except:
                pass
