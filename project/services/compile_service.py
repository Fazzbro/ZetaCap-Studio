import os
import subprocess
import imageio_ffmpeg
from moviepy import VideoFileClip

def compile_video_sync(video_configs, music_path=None, music_volume=0.5):
    """
    Synchronously compiles a series of video segments and adds optional background music
    using FFmpeg filtergraphs. Now supports screen-blend transitions between clips.
    """
    from ..core.config import config
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    import uuid
    output_path = os.path.join(output_dir, f"temp_compiled_video_{uuid.uuid4().hex[:8]}.mp4")
    
    if os.path.exists(output_path):
        os.remove(output_path)
        
    if not video_configs:
        raise ValueError("No active segments to compile.")

    # Use MoviePy instead of cv2 to correctly respect portrait rotation metadata
    with VideoFileClip(video_configs[0]['path']) as clip:
        target_w, target_h = clip.size
    
    if target_w == 0 or target_h == 0:
        target_w, target_h = 1080, 1920
        
    cmd = [ffmpeg_path, "-y"]
    
    for cfg in video_configs:
        cmd.extend(["-i", cfg['path']])
        
    # Only add transition if there are multiple DIFFERENT video files
    unique_videos = len(set([cfg['path'] for cfg in video_configs]))
    has_transition = os.path.exists(config.TRANSITION_VIDEO_PATH) and unique_videos > 1
    trans_idx = len(video_configs)
    
    if has_transition:
        cmd.extend(["-i", config.TRANSITION_VIDEO_PATH])
        
    # --- Gather input video properties ---
    with VideoFileClip(video_configs[0]['path']) as clip:
        target_w, target_h = clip.size
        rotation = getattr(clip, 'rotation', 0)
        
    transpose_filter = ""
    if rotation == 90:
        transpose_filter = "transpose=1,"
    elif rotation in (270, -90):
        transpose_filter = "transpose=2,"
    elif rotation == 180:
        transpose_filter = "transpose=2,transpose=2,"

    # --- Build complex filtergraph ---
    filter_parts = []
    concat_inputs = ""
    
    cut_times = []
    current_time = 0.0
    
    for i, cfg in enumerate(video_configs):
        clip = VideoFileClip(cfg['path'])
        dur = clip.duration
        has_audio = (clip.audio is not None)
        clip.close()
        
        start = max(0, cfg['start'])
        end = cfg['end'] if cfg['end'] > 0 else dur
        end = min(end, dur)
        seg_dur = max(0.01, end - start)
        
        if i < len(video_configs) - 1:
            current_time += seg_dur
            cut_times.append(current_time)
            
        v_filter = f"[{i}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,{transpose_filter}scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v{i}]"
        if has_audio:
            a_filter = f"[{i}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,aresample=44100[a{i}]"
        else:
            a_filter = f"aevalsrc=0:d={seg_dur}:s=44100[a{i}]"
        
        filter_parts.append(v_filter)
        filter_parts.append(a_filter)
        concat_inputs += f"[v{i}][a{i}]"
    
    filter_parts.append(f"{concat_inputs}concat=n={len(video_configs)}:v=1:a=1[base_v][base_a]")
    
    if has_transition:
        trans_dur = 0.256 # Known duration of the transition landscape.mov
        num_cuts = len(cut_times)
        
        v_splits = "".join([f"[tv{j}]" for j in range(num_cuts)])
        a_splits = "".join([f"[ta{j}]" for j in range(num_cuts)])
        
        filter_parts.append(f"[{trans_idx}:v]scale={target_w}:{target_h},split={num_cuts}{v_splits}")
        filter_parts.append(f"[{trans_idx}:a]aresample=44100,asplit={num_cuts}{a_splits}")
        
        last_v = "base_v"
        audio_mix_inputs = "[base_a]"
        
        for j, c_time in enumerate(cut_times):
            delay = max(0, c_time - (trans_dur / 2))
            
            # Video shift and blend (Screen mode)
            filter_parts.append(f"[tv{j}]setpts=PTS-STARTPTS+({delay}/TB)[tv_shift{j}]")
            out_v = f"blend_v{j}"
            filter_parts.append(f"[{last_v}][tv_shift{j}]blend=all_mode='screen':enable='between(t,{delay},{delay+trans_dur})'[{out_v}]")
            last_v = out_v
            
            # Audio delay
            delay_ms = int(delay * 1000)
            filter_parts.append(f"[ta{j}]adelay=delays='{delay_ms}|{delay_ms}':all=1[ta_shift{j}]")
            audio_mix_inputs += f"[ta_shift{j}]"
            
        filter_parts.append(f"{audio_mix_inputs}amix=inputs={num_cuts+1}:duration=first:dropout_transition=0[blend_a]")
        
        outv = f"[{last_v}]"
        outa = "[blend_a]"
    else:
        outv = "[base_v]"
        outa = "[base_a]"
    
    if music_path and os.path.exists(music_path):
        music_idx = trans_idx + 1 if has_transition else trans_idx
        cmd.extend(["-stream_loop", "-1", "-i", music_path])
        filter_parts.append(f"[{music_idx}:a]volume={music_volume},aresample=44100[mus]")
        filter_parts.append(f"{outa}[mus]amix=inputs=2:duration=first:dropout_transition=0[finala]")
        map_a = "[finala]"
    else:
        map_a = outa
        
    filtergraph = ";".join(filter_parts)
    
    cmd.extend([
        "-filter_complex", filtergraph,
        "-map", outv,
        "-map", map_a,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path
    ])
    
    print(f"[FFmpeg Filtergraph Compile] Running with transition={has_transition}")
    
    # Hide the terminal window on Windows
    creationflags = 0
    if os.name == 'nt':
        creationflags = subprocess.CREATE_NO_WINDOW
        
    result = subprocess.run(cmd, capture_output=True, text=True, stdin=subprocess.DEVNULL, creationflags=creationflags)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg Error:\n{result.stderr[-1000:]}")
        
    return output_path
