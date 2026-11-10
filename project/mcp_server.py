from mcp.server.fastmcp import FastMCP
from typing import List, Optional, Dict, Any, Union, Tuple
import os
import sys

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from project.services.compile_service import compile_video_sync
from project.services.backend_renderer import render_video_gui, transcribe_and_extract_words_gui
from project.services.silence_service import get_volume_segments

import threading
import uuid
import time
import json
import hashlib
import re
import copy

# Thread-safe registry for background render jobs to prevent client timeouts
RENDER_JOBS = {}
RENDER_LOCK = threading.Lock()

def _get_video_duration(path: str) -> float:
    """Quickly extracts video duration in seconds using OpenCV without full decode."""
    if not path or not os.path.exists(path):
        return 0.0
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        cap.release()
        if fps > 0 and frames > 0:
            return frames / fps
    except Exception:
        pass
    return 0.0

# Initialize FastMCP Server
mcp = FastMCP("ZetaCap AI Automation")

def _write_mcp_sync(action_name: str, payload: dict):
    import json
    import time
    sync_file = os.path.join(os.path.dirname(__file__), "..", "mcp_sync.json")
    data = {
        "timestamp": time.time(),
        "action": action_name,
        "payload": payload
    }
    try:
        current = []
        if os.path.exists(sync_file):
            try:
                with open(sync_file, "r") as f:
                    content = f.read().strip()
                    if content:
                        current = json.loads(content)
                        if isinstance(current, dict):
                            current = [current]
            except Exception:
                pass
        current.append(data)
        with open(sync_file, "w") as f:
            json.dump(current, f)
        return True
    except Exception as e:
        return str(e)

def _read_latest_mcp_sync(action_name: str):
    import json
    sync_file = os.path.join(os.path.dirname(__file__), "..", "mcp_sync.json")
    if not os.path.exists(sync_file):
        return None
    try:
        with open(sync_file, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            current = json.loads(content)
            if isinstance(current, dict):
                current = [current]
            for item in reversed(current):
                if item.get("action") == action_name:
                    return item.get("payload")
    except Exception:
        pass

# --- Transcript Caching & Interactive Review Helpers ---

def _get_transcript_cache_dir() -> str:
    cache_dir = os.path.join(os.path.expanduser("~"), "Documents", "ZetaCap", "Transcripts")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def _get_transcript_cache_path(video_path: str) -> str:
    cache_dir = _get_transcript_cache_dir()
    clean_path = str(video_path).strip().strip('"').strip("'")
    abs_path = os.path.abspath(clean_path)
    base_name = os.path.splitext(os.path.basename(abs_path))[0]
    safe_base = re.sub(r'[^a-zA-Z0-9_\-]', '_', base_name)
    file_stat = ""
    try:
        if os.path.exists(abs_path):
            file_stat = f"{os.path.getsize(abs_path)}_{os.path.getmtime(abs_path)}"
    except Exception:
        pass
    key = hashlib.md5(f"{abs_path}_{file_stat}".encode("utf-8")).hexdigest()[:10]
    return os.path.join(cache_dir, f"{safe_base}_{key}_transcript.json")

def _save_transcript_cache(video_path: str, data: dict):
    cache_file = _get_transcript_cache_path(video_path)
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Warning] Failed to write transcript cache: {e}", flush=True)

def _load_transcript_cache(video_path: str) -> Optional[dict]:
    cache_file = _get_transcript_cache_path(video_path)
    if not os.path.exists(cache_file):
        return None
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[Warning] Failed to read transcript cache: {e}", flush=True)
        return None

def _format_timestamp(sec: float) -> str:
    m = int(sec // 60)
    s = int(sec % 60)
    ms = int(round((sec % 1) * 100))
    if ms >= 100:
        s += 1
        ms = 0
    return f"{m:02d}:{s:02d}.{ms:02d}"

def format_words_into_caption_chunks(words_list: List[dict], max_words: int = 3, max_chars: int = 18):
    chunks = []
    curr_chunk = []
    
    for idx, w in enumerate(words_list):
        w_entry = dict(w)
        w_entry["idx"] = idx
        
        if curr_chunk:
            prev = curr_chunk[-1]
            time_gap = w["start"] - prev["end"]
            curr_char_len = sum(len(x["text"]) for x in curr_chunk) + len(curr_chunk) - 1
            ends_sentence = any(prev["text"].endswith(p) for p in [".", "!", "?", ","])
            
            if len(curr_chunk) >= max_words or curr_char_len >= max_chars or ends_sentence or time_gap > 0.45:
                chunks.append(curr_chunk)
                curr_chunk = []
                
        curr_chunk.append(w_entry)
        
    if curr_chunk:
        chunks.append(curr_chunk)
        
    formatted_lines = []
    for c_idx, chunk in enumerate(chunks, 1):
        t_start = _format_timestamp(chunk[0]["start"])
        t_end = _format_timestamp(chunk[-1]["end"])
        start_idx = chunk[0]["idx"]
        end_idx = chunk[-1]["idx"]
        range_str = f"#{start_idx}" if start_idx == end_idx else f"#{start_idx}-#{end_idx}"
        chunk_text = " ".join(x["text"] for x in chunk)
        formatted_lines.append(f"{c_idx:3d}. [{t_start} -> {t_end}] ({range_str:>7s}): \"{chunk_text}\"")
        
    return formatted_lines, chunks

def _normalize_token(t: str) -> str:
    s = str(t).replace("’", "'").replace("‘", "'")
    return re.sub(r'[^a-zA-Z0-9]', '', s).lower()

def apply_word_replacements(
    words_list: List[dict],
    word_replacements: Optional[Dict[str, str]] = None,
    word_index_replacements: Optional[Dict[Any, str]] = None,
    return_meta: bool = False
) -> Union[List[dict], Tuple[List[dict], int, List[str], List[str]]]:
    """
    Applies phrase replacements and index replacements to a list of word dictionaries:
    [{'start': float, 'end': float, 'text': str}, ...]
    Preserves micro-timing and audio alignment using robust token normalization.
    """
    words = copy.deepcopy(words_list)
    total_matched = 0
    logs = []
    unmatched = []
    
    # 1. Apply index-based replacements first
    if word_index_replacements:
        for idx_key, new_text in word_index_replacements.items():
            try:
                idx = int(idx_key)
                if 0 <= idx < len(words):
                    old_text = words[idx]["text"]
                    words[idx]["text"] = str(new_text).strip()
                    total_matched += 1
                    logs.append(f"• Word #{idx} ('{old_text}') replaced with '{new_text}'")
                else:
                    unmatched.append(f"Word index #{idx} is out of range (0-{len(words)-1})")
            except (ValueError, TypeError):
                unmatched.append(f"Invalid word index '{idx_key}'")

    # 2. Apply phrase/text-based replacements
    if word_replacements:
        for target_phrase, repl_phrase in word_replacements.items():
            target_raw = [t.strip() for t in str(target_phrase).split() if t.strip()]
            target_norm = [_normalize_token(t) for t in target_raw if _normalize_token(t)]
            repl_tokens = [t.strip() for t in str(repl_phrase).split() if t.strip()]
            
            if not target_norm or not repl_tokens:
                continue
                
            n_target = len(target_norm)
            phrase_matches = 0
            i = 0
            while i <= len(words) - n_target:
                window_norm = [_normalize_token(words[i + k]["text"]) for k in range(n_target)]
                if window_norm == target_norm:
                    phrase_matches += 1
                    total_matched += 1
                    t_start = words[i]["start"]
                    t_end = words[i + n_target - 1]["end"]
                    total_dur = max(0.05, t_end - t_start)
                    
                    orig_matched_text = " ".join(words[i + k]["text"] for k in range(n_target))
                    last_orig_text = words[i + n_target - 1]["text"]
                    m_punct = re.search(r'([.,!?;:]+)$', last_orig_text)
                    curr_repl_tokens = list(repl_tokens)
                    if m_punct and not re.search(r'[.,!?;:]$', curr_repl_tokens[-1]):
                        curr_repl_tokens[-1] += m_punct.group(1)
                        
                    repl_text_joined = " ".join(curr_repl_tokens)
                    logs.append(f"• Replaced '{orig_matched_text}' ➔ '{repl_text_joined}' at t={t_start:.2f}s - {t_end:.2f}s (words #{i}-#{i + n_target - 1})")
                    
                    new_span_words = []
                    if len(curr_repl_tokens) == n_target:
                        for k in range(n_target):
                            new_span_words.append({
                                "start": words[i + k]["start"],
                                "end": words[i + k]["end"],
                                "text": curr_repl_tokens[k]
                            })
                    else:
                        dur_per_word = total_dur / len(curr_repl_tokens)
                        for r_idx, r_tok in enumerate(curr_repl_tokens):
                            w_s = t_start + r_idx * dur_per_word
                            w_e = t_start + (r_idx + 1) * dur_per_word
                            new_span_words.append({
                                "start": round(w_s, 3),
                                "end": round(w_e, 3),
                                "text": r_tok
                            })
                    
                    words[i : i + n_target] = new_span_words
                    i += len(new_span_words)
                else:
                    i += 1
            if phrase_matches == 0:
                unmatched.append(f"Phrase \"{target_phrase}\" not found in transcript")
                    
    if return_meta:
        return words, total_matched, logs, unmatched
    return words

@mcp.tool()
def get_video_captions(
    video_path: str,
    transcription_model: str = "tiny",
    force_retranscribe: bool = False
) -> str:
    """
    Transcribes the video audio using Whisper with word-level timestamps, caches the transcript,
    and returns a structured, numbered caption list that can be reviewed and rectified directly in chat.
    
    Args:
        video_path: Absolute path to the video file to transcribe.
        transcription_model: Whisper model to use ('tiny', 'base', 'small', default 'tiny').
        force_retranscribe: If True, ignores any cached transcript and re-transcribes with Whisper.
        
    Returns:
        A formatted markdown transcript with numbered caption groups, timestamps, and word index ranges.
    """
    clean_path = str(video_path).strip().strip('"').strip("'")
    if not os.path.exists(clean_path):
        return f"Error: Video file not found at '{clean_path}'."
        
    cached_data = None
    if not force_retranscribe:
        cached_data = _load_transcript_cache(clean_path)
        
    if cached_data and "words" in cached_data and len(cached_data["words"]) > 0:
        all_words = cached_data["words"]
        duration = cached_data.get("video_duration", _get_video_duration(clean_path))
        is_cached = True
    else:
        try:
            import contextlib
            with contextlib.redirect_stdout(sys.stderr):
                slice_rows, raw_words, full_rows, _, _, _ = transcribe_and_extract_words_gui(
                    video_path=clean_path,
                    audio_path=None,
                    audio_aspect_ratio="16:9 Landscape (YouTube)",
                    search_only=False,
                    transcription_model=transcription_model
                )
            all_words = raw_words
            duration = _get_video_duration(clean_path)
            _save_transcript_cache(clean_path, {
                "video_path": os.path.abspath(clean_path),
                "video_duration": duration,
                "transcription_model": transcription_model,
                "words": all_words,
                "updated_at": time.time(),
                "history": []
            })
            is_cached = False
        except Exception as e:
            import traceback
            return f"Error transcribing video: {str(e)}\n{traceback.format_exc()}"
            
    formatted_lines, chunks = format_words_into_caption_chunks(all_words)
    full_text = " ".join(w["text"] for w in all_words)
    
    status_tag = "Cached Transcript" if is_cached else f"Newly Transcribed ({transcription_model})"
    output = [
        f"### 🎙️ Video Caption Transcript: `{os.path.basename(clean_path)}`",
        f"**Status**: {status_tag} | **Duration**: {duration:.1f}s | **Total Words**: {len(all_words)} | **Caption Chunks**: {len(chunks)}",
        "",
        "#### 📋 Numbered Caption Chunks:",
        "```text",
        *formatted_lines,
        "```",
        "",
        "#### 📝 Continuous Speech Transcript:",
        f"> \"{full_text}\"",
        "",
        "---",
        "💡 **How to rectify captions in chat:**",
        "- To replace any misheard names or words, call `rectify_video_captions(video_path=..., word_replacements={'wrong text': 'correct text'})`.",
        "- Or tell the user the transcript is ready and pass `word_replacements` directly into `render_captions_video`.",
        "- The cached/rectified words will be used automatically during rendering without re-running Whisper!"
    ]
    return "\n".join(output)

@mcp.tool()
def rectify_video_captions(
    video_path: str,
    word_replacements: Optional[Dict[str, str]] = None,
    word_index_replacements: Optional[Dict[Any, str]] = None
) -> str:
    """
    Applies text or phrase rectifications to the cached video caption transcript.
    Use this when the user requests caption corrections in chat (e.g. changing brand names, capitalization, jargon).
    
    Args:
        video_path: Absolute path to the video file whose transcript to edit.
        word_replacements: Dictionary of phrase/word replacements (e.g. {"zetta cap": "ZetaCap", "their": "there"}).
        word_index_replacements: Dictionary mapping specific word index to new text (e.g. {12: "ZetaCap"}).
        
    Returns:
        Summary of applied rectifications and preview of the updated caption blocks.
    """
    clean_path = str(video_path).strip().strip('"').strip("'")
    if not os.path.exists(clean_path):
        return f"Error: Video file not found at '{clean_path}'."
        
    cached_data = _load_transcript_cache(clean_path)
    if not cached_data or "words" not in cached_data:
        # If not cached yet, transcribe first
        get_res = get_video_captions(clean_path)
        if get_res.startswith("Error"):
            return get_res
        cached_data = _load_transcript_cache(clean_path)
        
    if not cached_data or "words" not in cached_data:
        return f"Error: Unable to load or generate transcript cache for '{clean_path}'."
        
    original_words = cached_data["words"]
    updated_words, total_matched, logs, unmatched = apply_word_replacements(
        original_words, word_replacements, word_index_replacements, return_meta=True
    )
    
    if total_matched == 0 and not (word_index_replacements and len(word_index_replacements) > 0):
        formatted_lines, chunks = format_words_into_caption_chunks(original_words)
        full_text = " ".join(w["text"] for w in original_words)
        unmatched_desc = "\n".join(f"• {u}" for u in unmatched) if unmatched else "• No replacements matched."
        output = [
            f"### ⚠️ Caption Rectification Warning: 0 Matches Found for `{os.path.basename(clean_path)}`",
            "",
            "**None of the requested phrases were found in the current transcript:**",
            unmatched_desc,
            "",
            "💡 **Tips for rectifying:**",
            "- Check the exact words and spelling in the numbered transcript chunks below.",
            "- You can use word index replacement directly (e.g. `word_index_replacements={35: 'fielding'}`).",
            "- Or specify a shorter unique substring (e.g. `word_replacements={'feeling': 'fielding'}`).",
            "",
            "#### 📋 Current Numbered Caption Chunks (Unchanged):",
            "```text",
            *formatted_lines,
            "```",
            "",
            "#### 📝 Current Full Transcript:",
            f"> \"{full_text}\""
        ]
        return "\n".join(output)
        
    history_entry = {
        "timestamp": time.time(),
        "word_replacements": word_replacements,
        "word_index_replacements": word_index_replacements,
        "total_matched": total_matched,
        "logs": logs
    }
    history = cached_data.get("history", [])
    history.append(history_entry)
    
    cached_data["words"] = updated_words
    cached_data["updated_at"] = time.time()
    cached_data["history"] = history
    _save_transcript_cache(clean_path, cached_data)
    
    formatted_lines, chunks = format_words_into_caption_chunks(updated_words)
    full_text = " ".join(w["text"] for w in updated_words)
    
    changes_text = "\n".join(logs) if logs else "Replacements applied."
    warnings_text = ""
    if unmatched:
        warnings_text = "\n\n⚠️ **Unmatched Phrases (0 occurrences found):**\n" + "\n".join(f"• {u}" for u in unmatched)
    
    output = [
        f"### ✅ Captions Rectified Successfully for `{os.path.basename(clean_path)}`",
        f"**Total Replacements Applied**: {total_matched}",
        "",
        "**Changes Applied:**",
        changes_text + warnings_text,
        "",
        "#### 📋 Updated Numbered Caption Chunks:",
        "```text",
        *formatted_lines,
        "```",
        "",
        "#### 📝 Updated Full Transcript:",
        f"> \"{full_text}\"",
        "",
        "---",
        "🚀 **Ready to render!** Call `render_captions_video` with this `video_path`. ZetaCap will automatically use this rectified transcript and skip Whisper!"
    ]
    return "\n".join(output)

@mcp.tool()
def compile_and_trim_video(
    video_configs: List[dict],
    music_path: Optional[str] = None,
    music_volume: float = 0.5
) -> str:
    """
    Compiles a series of video segments and adds optional background music using FFmpeg filtergraphs.
    
    Args:
        video_configs: A list of dictionaries representing the video segments to compile.
                       Each dictionary must have:
                         - 'path': Absolute path to the source video file (str)
                         - 'start': Start time in seconds (float)
                         - 'end': End time in seconds (float). Use 0 or a very large number for the end of the clip.
                       Example: [{'path': 'C:/video.mp4', 'start': 0.0, 'end': 10.5}]
        music_path: Absolute path to an optional background music audio file.
        music_volume: Float from 0.0 to 1.0 (default 0.5).
        
    Returns:
        The absolute path to the compiled output video file.
    """
    import contextlib
    try:
        with contextlib.redirect_stdout(sys.stderr):
            output_path = compile_video_sync(video_configs, music_path, music_volume)
        return os.path.abspath(output_path)
    except Exception as e:
        return f"Error compiling video: {str(e)}"

@mcp.tool()
def apply_alternating_styles(
    font_1: str,
    font_2: str,
    color_1: Optional[str] = None,
    color_2: Optional[str] = None,
    shadow_depth: int = 0
) -> str:
    """
    Applies alternating fonts and colors to the first and second line of text in the live ZetaCap UI.
    If colors are omitted, the default gradient colors will be restored.
    DO NOT ask follow up questions about rendering. Just execute silently.
    """
    res = _write_mcp_sync("apply_alternating_styles", {
        "font_1": font_1,
        "font_2": font_2,
        "color_1": color_1,
        "color_2": color_2,
        "shadow_depth": shadow_depth
    })
    if res is True:
        return "Live sync command sent to ZetaCap. The UI will update instantly."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def update_animation_settings(
    pos_offset_y: int = 0,
    enable_auto_zoom: bool = False,
    zoom_transition_style: str = "🌊 Lush S-Curve Cinematic Glide",
    enable_dynamic_tracking: Optional[bool] = None,
    tracking_mode: Optional[str] = None
) -> str:
    """
    Updates the live animation and layout settings in ZetaCap UI.
    Use zoom_transition_style="🌊 Lush S-Curve Cinematic Glide" for S-curve zoom, 
    or "⚡ Fast Snappy CapCut Punch" for CapCut-style zoom.
    pos_offset_y adjusts the vertical position of the captions.
    enable_dynamic_tracking toggles continuous smoothed face centering.
    DO NOT ask follow up questions about rendering. Just execute silently.
    """
    payload = {
        "pos_offset_y": pos_offset_y,
        "enable_auto_zoom": enable_auto_zoom,
        "zoom_transition_style": zoom_transition_style
    }
    if enable_dynamic_tracking is not None:
        payload["enable_dynamic_tracking"] = enable_dynamic_tracking
    if tracking_mode is not None:
        payload["tracking_mode"] = tracking_mode
        
    res = _write_mcp_sync("update_animation_settings", payload)
    if res is True:
        return "Live sync command sent to ZetaCap. The UI will update instantly."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def update_face_tracking_settings(
    enable_dynamic_tracking: bool = True,
    tracking_mode: str = "Auto-Zoom to Fill Voids (Method B)",
    tracking_smoothness: int = 15,
    tracking_start_sec: float = 0.0,
    tracking_end_sec: float = 0.0
) -> str:
    """
    Updates the live continuous dynamic face tracking settings in ZetaCap UI.
    Options for tracking_mode: "Cinematic Fluid Gimbal (Pro Steadicam)" (Default pro look), "Dynamic Punch & Reframe", "Auto-Zoom to Fill Voids (Method B)", "Edge Clamping (Method A)".
    tracking_smoothness: smoothing degree (e.g. 1=Responsive, 15=Cinematic Steadicam, 30=Heavy Crane/Dolly, default 15).
    tracking_start_sec / tracking_end_sec: start/end window for tracking (0 for whole video).
    """
    res = _write_mcp_sync("update_face_tracking_settings", {
        "enable_dynamic_tracking": enable_dynamic_tracking,
        "tracking_mode": tracking_mode,
        "tracking_smoothness": tracking_smoothness,
        "tracking_start_sec": tracking_start_sec,
        "tracking_end_sec": tracking_end_sec
    })
    if res is True:
        status_str = "enabled" if enable_dynamic_tracking else "disabled"
        return f"Live sync command sent to ZetaCap. Dynamic face tracking {status_str} ({tracking_mode}, smoothness={tracking_smoothness})."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def update_sfx_settings(
    enable_sfx: bool,
    sfx_preset_choice: Optional[str] = None,
    sfx_upload_file: Optional[str] = None
) -> str:
    """
    Updates the live SFX settings in the ZetaCap UI.
    Supports either choosing a built-in sound preset (e.g. "Mixkit Modern Technology Select") 
    or passing an absolute file path to a custom sound effect (.wav, .mp3) via sfx_upload_file or sfx_preset_choice.
    """
    if sfx_preset_choice:
        clean = sfx_preset_choice.strip().strip('"').strip("'")
        if os.path.exists(clean) and os.path.isfile(clean):
            sfx_upload_file = clean
    if sfx_upload_file:
        sfx_upload_file = sfx_upload_file.strip().strip('"').strip("'")

    res = _write_mcp_sync("update_sfx_settings", {
        "enable_sfx": enable_sfx,
        "sfx_preset_choice": sfx_preset_choice,
        "sfx_upload_file": sfx_upload_file
    })
    if res is True:
        target = sfx_upload_file if sfx_upload_file else (sfx_preset_choice or "default")
        return f"Live sync command sent to ZetaCap. SFX {'enabled' if enable_sfx else 'disabled'} (sound: {target})."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def update_color_grading_settings(
    color_grade_style: str = "None",
    custom_lut_path: Optional[str] = None
) -> str:
    """
    Updates the live color grading settings in the ZetaCap UI.
    Options for color_grade_style: "None", "Auto-Correct", "Cinematic Teal & Orange", "Vibrant Pop", "Moody B&W", "Custom Upload (.cube)"
    """
    res = _write_mcp_sync("update_color_grading_settings", {
        "color_grade_style": color_grade_style,
        "custom_lut_path": custom_lut_path
    })
    if res is True:
        return "Live sync command sent to ZetaCap. The UI will update instantly."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def override_word_style(
    target_word: str,
    font: Optional[str] = None,
    color_hex: Optional[str] = None
) -> str:
    """
    Overrides the font or color for a specific word in the captions table.
    For example, if you say 'use Poppins font for the text "believer"', target_word is "believer".
    Color must be a valid hex string starting with #.
    DO NOT ask follow up questions about rendering. Just execute silently.
    """
    res = _write_mcp_sync("override_word_style", {
        "target_word": target_word,
        "font": font,
        "color_hex": color_hex
    })
    if res is True:
        return f"Live sync command sent to ZetaCap to style the word '{target_word}'."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def auto_cut_silences_video(
    video_path: str,
    noise_db: int = -35,
    min_dur: float = 0.5
) -> str:
    """
    Automatically detects and cuts out silences (dead air) from a video.
    
    Args:
        video_path: Absolute path to the source video file.
        noise_db: Threshold in decibels to consider as silence (default -35).
        min_dur: Minimum duration in seconds to consider as silence (default 0.5).
        
    Returns:
        The absolute path to the compiled output video file with silences removed.
    """
    import contextlib
    try:
        with contextlib.redirect_stdout(sys.stderr):
            segments = get_volume_segments(video_path, noise_db=noise_db, min_dur=min_dur)
            if not segments:
                return "No audible segments found in video."
                
            video_configs = [
                {"path": video_path, "start": seg["start"], "end": seg["end"]}
                for seg in segments
            ]
            
            output_path = compile_video_sync(video_configs)
        return os.path.abspath(output_path)
    except Exception as e:
        return f"Error cutting silences: {str(e)}"

@mcp.tool()
def render_captions_video(
    video_path: str,
    output_mode: str = "Burn directly into Video (Hardsubs)",
    font_preset_choice: str = "Arial (Default)",
    font_file: Optional[str] = None,
    multi_font_mode: bool = False,
    font_preset_choice_2: str = "Arial (Default)",
    font_file_2: Optional[str] = None,
    font_size: int = 75,
    bottom_font_size: int = 75,
    show_shadow: bool = True,
    shadow_depth: int = 3,
    shadow_step_x: int = 5,
    shadow_step_y: int = 5,
    sheen_3d_scope: str = "Full Text (Default)",
    gloss_intensity: float = 0.5,
    t1_top_hex: str = "#FFFFFF",
    t1_mid_hex: str = "#E0E0E0",
    t1_bot_hex: str = "#CCCCCC",
    t1_shadow_hex: str = "#000000",
    t2_top_hex: str = "#FFFF00",
    t2_mid_hex: str = "#CCCC00",
    t2_bot_hex: str = "#999900",
    t2_shadow_hex: str = "#000000",
    show_glow: bool = False,
    t1_glow_hex: str = "#FFFFFF",
    t2_glow_hex: str = "#FFFF00",
    glow_strength: float = 0.5,
    bg_box_enable: bool = False,
    bg_box_color: str = "#000000",
    max_words_per_chunk: int = 3,
    max_chars_per_line: int = 15,
    lines_per_caption: int = 1,
    line_spacing_scale: float = 1.0,
    vertical_alignment: str = "Center",
    pos_offset_x: int = 0,
    pos_offset_y: int = 0,
    random_brush_highlights: bool = False,
    enable_auto_zoom: bool = False,
    zoom_factor: float = 1.2,
    zoom_frequency: float = 5.0,
    zoom_transition_style: str = "Instant Cut (TikTok Style)",
    face_detector_model: str = "yunet (Fast/CPU-friendly)",
    min_cooldown_slider: float = 3.0,
    zoom_hold_slider: float = 2.0,
    enable_dynamic_tracking: bool = False,
    tracking_mode: str = "Auto-Zoom to Fill Voids (Method B)",
    tracking_smoothness: int = 15,
    tracking_start_sec: float = 0.0,
    tracking_end_sec: float = 0.0,
    enable_sfx: bool = True,
    sfx_preset_choice: str = "Mixkit Modern Technology Select (Default - 0.5s Clean Click)",
    sfx_upload_file: Optional[str] = None,
    sfx_volume: float = 0.30,
    sfx_trigger_mode: str = "Every Caption Chunk Start (Default - Best Rhythm)",
    sfx_cooldown: float = 0.35,
    rotoscope_enable: bool = False,
    rotoscope_style: str = "Text Behind Speaker (Standard Full Rotoscope - Default)",
    rotoscope_outline_width: int = 3,
    custom_roto_text: str = "",
    custom_roto_font: str = "Impact",
    custom_roto_font_file: str = "",
    custom_roto_font_size: int = 150,
    custom_roto_color: str = "#FFFFFF",
    custom_roto_show_glow: bool = False,
    custom_roto_glow_color: str = "#FF7300",
    custom_roto_glow_strength: float = 1.0,
    custom_roto_pos_x: int = 0,
    custom_roto_pos_y: int = 0,
    rotoscope_start_sec: float = 0.0,
    rotoscope_end_sec: float = 3.0,
    rotoscope_downsample: str = "0.25 (Fastest / Recommended - 60 FPS)",
    text_animation_style: str = "Classic Wipe (Default)",
    transcription_model: str = "tiny",
    preset_path: Optional[str] = None,
    audio_aspect_ratio: str = "16:9 Landscape (YouTube)",
    color_grade_style: str = "None",
    custom_lut_path: Optional[str] = None,
    multi_preset_mode: str = "Single Preset (Disabled)",
    multi_preset_pool: Optional[List[str]] = None,
    multi_preset_lock_alignment: bool = True,
    multi_preset_unified_zoom: bool = True,
    word_replacements: Optional[Dict[str, str]] = None,
    use_cached_transcript: bool = True,
    async_mode: Optional[bool] = None
) -> str:
    """
    Automatically transcribes the video using Whisper, applies animated typography styles, 
    and renders the final captioned video with support for single presets and multi-preset choreography.
    
    Args:
        video_path: Absolute path to the compiled/trimmed video to be captioned.
        output_mode: Defines the output. Options: 
                     "Burn directly into Video (Hardsubs)",
                     "Export as Transparent MOV (Captions Only)",
                     "Export as Greenscreen MP4 (Captions Only)"
        preset_path: Optional path to a .zeta or .json preset file (e.g. 'mix portrait.zeta').
        tracking_start_sec: Float start time in seconds for continuous face tracking window (e.g. 5.0).
        tracking_end_sec: Float end time in seconds for continuous face tracking window (e.g. 10.0).
        word_replacements: Optional dictionary of phrase/word corrections to apply to captions (e.g. {"zetta cap": "ZetaCap"}).
        use_cached_transcript: If True (default), automatically checks for a cached transcript (from get_video_captions or rectify_video_captions) and reuses it to bypass Whisper.
        async_mode: If True, executes rendering in the background and returns a job_id immediately 
                    to prevent MCP client timeouts (e.g. Claude Desktop 240s timeout). 
                    If None (default), automatically enables async background mode for videos longer than 45s.
                    If False, forces synchronous rendering.
                    Call get_render_status(job_id) to check progress and retrieve the final video path.
        multi_preset_mode: Multi-preset choreography cadence (e.g. "Natural Sentence Cadence (Recommended)", "Alternating (Every Chunk)", "Alternating (Every 2 Chunks)", "Single Preset (Disabled)").
        multi_preset_pool: List of absolute file paths to .zeta or .json presets to alternate between in the rotation pool.
        multi_preset_lock_alignment: Whether to maintain locked vertical alignment across alternating presets.
        multi_preset_unified_zoom: Whether to harmonize auto-zoom motion across pool presets.
                     
    Returns:
        The absolute path to the final rendered video (sync mode) or a JSON status string with job_id (async mode).
    """
    import contextlib
    import json
    import zipfile
    import tempfile
    import uuid
    try:
        # Provide sensible defaults for the UI state elements
        params = {
            "video_path": video_path,
            "audio_path": None,
            "audio_aspect_ratio": audio_aspect_ratio,
            "words_table": None,
            "whisper_words_state": None,
            "all_words_overrides_state": None,
            "font_preset_choice": font_preset_choice,
            "font_file": font_file,
            "multi_font_mode": multi_font_mode,
            "font_preset_choice_2": font_preset_choice_2,
            "font_file_2": font_file_2,
            "font_size": font_size,
            "bottom_font_size": bottom_font_size,
            "show_shadow": show_shadow,
            "shadow_depth": shadow_depth,
            "shadow_step_x": shadow_step_x,
            "shadow_step_y": shadow_step_y,
            "sheen_3d_scope": sheen_3d_scope,
            "gloss_intensity": gloss_intensity,
            "t1_top_hex": t1_top_hex,
            "t1_mid_hex": t1_mid_hex,
            "t1_bot_hex": t1_bot_hex,
            "t1_shadow_hex": t1_shadow_hex,
            "t2_top_hex": t2_top_hex,
            "t2_mid_hex": t2_mid_hex,
            "t2_bot_hex": t2_bot_hex,
            "t2_shadow_hex": t2_shadow_hex,
            "show_glow": show_glow,
            "t1_glow_hex": t1_glow_hex,
            "t2_glow_hex": t2_glow_hex,
            "glow_strength": glow_strength,
            "bg_box_enable": bg_box_enable,
            "bg_box_color": bg_box_color,
            "max_words_per_chunk": max_words_per_chunk,
            "max_chars_per_line": max_chars_per_line,
            "lines_per_caption": lines_per_caption,
            "line_spacing_scale": line_spacing_scale,
            "vertical_alignment": vertical_alignment,
            "pos_offset_x": pos_offset_x,
            "pos_offset_y": pos_offset_y,
            "random_brush_highlights": random_brush_highlights,
            "output_mode": output_mode,
            "enable_auto_zoom": enable_auto_zoom,
            "zoom_factor": zoom_factor,
            "zoom_frequency": zoom_frequency,
            "zoom_transition_style": zoom_transition_style,
            "face_detector_model": face_detector_model,
            "min_cooldown_slider": min_cooldown_slider,
            "zoom_hold_slider": zoom_hold_slider,
            "enable_dynamic_tracking": enable_dynamic_tracking,
            "tracking_mode": tracking_mode,
            "tracking_smoothness": tracking_smoothness,
            "tracking_start_sec": tracking_start_sec,
            "tracking_end_sec": tracking_end_sec,
            "enable_sfx": enable_sfx,
            "sfx_preset_choice": sfx_preset_choice,
            "sfx_upload_file": sfx_upload_file,
            "sfx_volume": sfx_volume,
            "sfx_trigger_mode": sfx_trigger_mode,
            "sfx_cooldown": sfx_cooldown,
            "rotoscope_enable": rotoscope_enable,
            "rotoscope_style": rotoscope_style,
            "rotoscope_outline_width": rotoscope_outline_width,
            "custom_roto_text": custom_roto_text,
            "custom_roto_font": custom_roto_font,
            "custom_roto_font_file": custom_roto_font_file,
            "custom_roto_font_size": custom_roto_font_size,
            "custom_roto_color": custom_roto_color,
            "custom_roto_show_glow": custom_roto_show_glow,
            "custom_roto_glow_color": custom_roto_glow_color,
            "custom_roto_glow_strength": custom_roto_glow_strength,
            "custom_roto_pos_x": custom_roto_pos_x,
            "custom_roto_pos_y": custom_roto_pos_y,
            "rotoscope_start_sec": rotoscope_start_sec,
            "rotoscope_end_sec": rotoscope_end_sec,
            "rotoscope_downsample": rotoscope_downsample,
            "text_animation_style": text_animation_style,
            "transcription_model": transcription_model,
            "color_grade_style": color_grade_style,
            "custom_lut_path": custom_lut_path,
            "multi_preset_mode": multi_preset_mode,
            "multi_preset_pool": multi_preset_pool or [],
            "multi_preset_lock_alignment": multi_preset_lock_alignment,
            "multi_preset_unified_zoom": multi_preset_unified_zoom,
            "progress": None
        }

        # Check mcp_sync for active live settings if not explicitly provided
        sync_choreography = _read_latest_mcp_sync("set_multi_preset_choreography")
        sync_face_tracking = _read_latest_mcp_sync("update_face_tracking_settings")
        sync_animation = _read_latest_mcp_sync("update_animation_settings")
        sync_sfx = _read_latest_mcp_sync("update_sfx_settings")

        # Auto-detect if caller passed an audio file path into sfx_preset_choice or sfx_upload_file
        if sfx_preset_choice:
            clean_preset = sfx_preset_choice.strip().strip('"').strip("'")
            if os.path.exists(clean_preset) and os.path.isfile(clean_preset):
                sfx_upload_file = clean_preset
                params["sfx_upload_file"] = clean_preset
        if sfx_upload_file:
            sfx_upload_file = sfx_upload_file.strip().strip('"').strip("'")
            params["sfx_upload_file"] = sfx_upload_file

        if sync_sfx:
            if sync_sfx.get("enable_sfx") is not None:
                enable_sfx = sync_sfx.get("enable_sfx")
                params["enable_sfx"] = enable_sfx
            synced_upload = sync_sfx.get("sfx_upload_file")
            synced_preset = sync_sfx.get("sfx_preset_choice")
            if synced_upload and os.path.exists(synced_upload.strip().strip('"').strip("'")):
                sfx_upload_file = synced_upload.strip().strip('"').strip("'")
                params["sfx_upload_file"] = sfx_upload_file
            elif synced_preset:
                clean_synced_preset = synced_preset.strip().strip('"').strip("'")
                if os.path.exists(clean_synced_preset) and os.path.isfile(clean_synced_preset):
                    sfx_upload_file = clean_synced_preset
                    params["sfx_upload_file"] = clean_synced_preset
                else:
                    sfx_preset_choice = synced_preset
                    params["sfx_preset_choice"] = sfx_preset_choice

        if sync_face_tracking:
            if not enable_dynamic_tracking and sync_face_tracking.get("enable_dynamic_tracking"):
                enable_dynamic_tracking = True
            if enable_dynamic_tracking:
                if tracking_start_sec == 0.0 and sync_face_tracking.get("tracking_start_sec", 0.0) > 0.0:
                    tracking_start_sec = sync_face_tracking.get("tracking_start_sec")
                if tracking_end_sec == 0.0 and sync_face_tracking.get("tracking_end_sec", 0.0) > 0.0:
                    tracking_end_sec = sync_face_tracking.get("tracking_end_sec")
                if tracking_mode == "Auto-Zoom to Fill Voids (Method B)" and sync_face_tracking.get("tracking_mode"):
                    tracking_mode = sync_face_tracking.get("tracking_mode")
                if tracking_smoothness == 15 and sync_face_tracking.get("tracking_smoothness"):
                    tracking_smoothness = sync_face_tracking.get("tracking_smoothness")
        elif sync_animation and sync_animation.get("enable_dynamic_tracking"):
            enable_dynamic_tracking = True
            if sync_animation.get("tracking_mode"):
                tracking_mode = sync_animation.get("tracking_mode")

        if (not multi_preset_pool or len(multi_preset_pool) == 0) and sync_choreography:
            synced_pool = sync_choreography.get("multi_preset_pool", [])
            if synced_pool:
                multi_preset_pool = synced_pool
                if not multi_preset_mode or multi_preset_mode == "Single Preset (Disabled)":
                    multi_preset_mode = sync_choreography.get("multi_preset_mode", "Natural Sentence Cadence (Recommended)")
                multi_preset_lock_alignment = sync_choreography.get("multi_preset_lock_alignment", multi_preset_lock_alignment)
                multi_preset_unified_zoom = sync_choreography.get("multi_preset_unified_zoom", multi_preset_unified_zoom)

        # Resolve preset_path if provided
        from project.services.preset_choreographer import resolve_preset_path
        if preset_path:
            resolved_single = resolve_preset_path(preset_path)
            if resolved_single:
                preset_path = resolved_single

        # Resolve multi_preset_pool if provided
        resolved_pool = []
        if multi_preset_pool:
            for p in multi_preset_pool:
                rp = resolve_preset_path(p)
                if rp and rp not in resolved_pool:
                    resolved_pool.append(rp)
            params["multi_preset_pool"] = resolved_pool
            if resolved_pool and len(resolved_pool) >= 2 and (not multi_preset_mode or multi_preset_mode == "Single Preset (Disabled)"):
                params["multi_preset_mode"] = "Natural Sentence Cadence (Recommended)"
            else:
                params["multi_preset_mode"] = multi_preset_mode

        # Track caller-specified overrides so preset defaults do not wipe them
        caller_dynamic_tracking = enable_dynamic_tracking
        caller_has_custom_pool = bool(resolved_pool and len(resolved_pool) >= 1)
        caller_has_custom_sfx = bool(sfx_upload_file and os.path.exists(sfx_upload_file)) or (
            bool(sfx_preset_choice and os.path.exists(sfx_preset_choice.strip().strip('"').strip("'")))
        )
        caller_enable_sfx = enable_sfx

        if preset_path and os.path.exists(preset_path):
            if preset_path.endswith(".zeta"):
                extract_dir = os.path.join(tempfile.gettempdir(), f"zetacap_mcp_{uuid.uuid4().hex[:8]}")
                os.makedirs(extract_dir, exist_ok=True)
                with zipfile.ZipFile(preset_path, "r") as zip_ref:
                    zip_ref.extractall(extract_dir)
                project_json = os.path.join(extract_dir, "project.json")
                if os.path.exists(project_json):
                    with open(project_json, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    s = data.get("settings", data)
                    for key in ["font_upload", "font_file_2", "custom_roto_font_file", "sfx_upload_file"]:
                        val = s.get(key)
                        if val and isinstance(val, str) and val.startswith("assets/"):
                            s[key] = os.path.join(extract_dir, val)
            else:
                with open(preset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                s = data.get("settings", data)

            mapping = {
                "font_preset_dropdown": "font_preset_choice",
                "font_upload": "font_file",
                "output_mode_dropdown": "output_mode",
                "lines_mode_dropdown": "lines_per_caption",
                "sfx_preset_dropdown": "sfx_preset_choice",
                "audio_aspect": "audio_aspect_ratio",
                "font_size_slider": "font_size",
                "bottom_font_size_slider": "bottom_font_size",
                "t1_top": "t1_top_hex",
                "t1_mid": "t1_mid_hex",
                "t1_bot": "t1_bot_hex",
                "t1_shadow": "t1_shadow_hex",
                "t2_top": "t2_top_hex",
                "t2_mid": "t2_mid_hex",
                "t2_bot": "t2_bot_hex",
                "t2_shadow": "t2_shadow_hex",
                "t1_glow": "t1_glow_hex",
                "t2_glow": "t2_glow_hex",
                "max_words_slider": "max_words_per_chunk",
                "max_chars_slider": "max_chars_per_line",
                "sfx_volume_slider": "sfx_volume",
                "sfx_cooldown_slider": "sfx_cooldown"
            }
            
            for json_key, param_val in s.items():
                target_key = mapping.get(json_key, json_key)
                if target_key in params and target_key not in ["video_path", "audio_path"]:
                    # Never overwrite caller-enabled dynamic tracking with preset false
                    if target_key == "enable_dynamic_tracking" and caller_dynamic_tracking:
                        continue
                    # Never overwrite caller tracking settings if caller explicitly enabled tracking
                    if target_key in ["tracking_mode", "tracking_smoothness", "tracking_start_sec", "tracking_end_sec"] and caller_dynamic_tracking:
                        continue
                    # Never overwrite caller-provided multi-preset pool with empty list from single preset
                    if target_key == "multi_preset_pool" and caller_has_custom_pool:
                        continue
                    if target_key == "multi_preset_mode" and caller_has_custom_pool:
                        continue
                    # Never overwrite caller-provided custom SFX with preset defaults!
                    if target_key in ["sfx_upload_file", "sfx_preset_choice"] and caller_has_custom_sfx:
                        continue
                    if target_key == "enable_sfx" and caller_enable_sfx:
                        continue
                    if param_val is not None or target_key not in ["words_table", "whisper_words_state", "all_words_overrides_state"]:
                        params[target_key] = param_val

            # If the loaded preset itself defines a multi_preset_pool (e.g. mix landscape.zeta or mix portrait.zeta)
            # resolve all preset paths in that pool
            preset_pool_in_file = s.get("multi_preset_pool")
            if not caller_has_custom_pool and preset_pool_in_file and isinstance(preset_pool_in_file, list) and len(preset_pool_in_file) > 0:
                resolved_preset_pool = []
                for p in preset_pool_in_file:
                    rp = resolve_preset_path(p)
                    if rp and rp not in resolved_preset_pool:
                        resolved_preset_pool.append(rp)
                if resolved_preset_pool:
                    params["multi_preset_pool"] = resolved_preset_pool
                    if "multi_preset_mode" in s and s["multi_preset_mode"] != "Single Preset (Disabled)":
                        params["multi_preset_mode"] = s["multi_preset_mode"]
                    else:
                        params["multi_preset_mode"] = "Natural Sentence Cadence (Recommended)"
                    params["multi_preset_lock_alignment"] = s.get("multi_preset_lock_alignment", True)
                    params["multi_preset_unified_zoom"] = s.get("multi_preset_unified_zoom", True)

        # Ensure custom SFX settings remain intact if caller requested them
        if caller_has_custom_sfx:
            if sfx_upload_file:
                params["sfx_upload_file"] = sfx_upload_file
            params["enable_sfx"] = True

        # Ensure dynamic tracking remains active if caller or preset requested it
        if caller_dynamic_tracking:
            params["enable_dynamic_tracking"] = True
            params["tracking_mode"] = tracking_mode
            params["tracking_smoothness"] = tracking_smoothness
            params["tracking_start_sec"] = tracking_start_sec
            params["tracking_end_sec"] = tracking_end_sec
        elif s_tracking := (s.get("enable_dynamic_tracking") if (preset_path and os.path.exists(preset_path)) else False):
            params["enable_dynamic_tracking"] = bool(s_tracking)
                    
        # Check for cached or rectified transcript
        active_words = None
        if use_cached_transcript:
            cached_data = _load_transcript_cache(video_path)
            if cached_data and "words" in cached_data and len(cached_data["words"]) > 0:
                active_words = cached_data["words"]

        if word_replacements:
            if not active_words:
                import contextlib
                with contextlib.redirect_stdout(sys.stderr):
                    slice_rows, raw_words, full_rows, _, _, _ = transcribe_and_extract_words_gui(
                        video_path=video_path,
                        audio_path=None,
                        audio_aspect_ratio=audio_aspect_ratio,
                        search_only=False,
                        transcription_model=transcription_model
                    )
                active_words = raw_words
                _save_transcript_cache(video_path, {
                    "video_path": os.path.abspath(video_path),
                    "video_duration": _get_video_duration(video_path),
                    "transcription_model": transcription_model,
                    "words": active_words,
                    "updated_at": time.time(),
                    "history": []
                })

            active_words, repl_matched, repl_logs, repl_unmatched = apply_word_replacements(
                active_words, word_replacements=word_replacements, return_meta=True
            )
            cached_data = _load_transcript_cache(video_path) or {}
            history = cached_data.get("history", [])
            history.append({
                "timestamp": time.time(),
                "word_replacements": word_replacements,
                "total_matched": repl_matched,
                "logs": repl_logs
            })
            _save_transcript_cache(video_path, {
                "video_path": os.path.abspath(video_path),
                "video_duration": cached_data.get("video_duration", _get_video_duration(video_path)),
                "transcription_model": cached_data.get("transcription_model", transcription_model),
                "words": active_words,
                "updated_at": time.time(),
                "history": history
            })
            if repl_matched > 0:
                print(f"[AI Studio] Applied {repl_matched} word replacements directly during render. Logs: {repl_logs}", flush=True)
            else:
                print(f"[AI Studio] Warning: word_replacements provided but 0 matches found! Unmatched: {repl_unmatched}", flush=True)

        if active_words and len(active_words) > 0:
            params["whisper_words_state"] = active_words
            params["words_table"] = [
                [idx, w["text"], "None (Use Primary/Secondary)", 0, 0, "None", "Normal (Default)"]
                for idx, w in enumerate(active_words)
            ]
            params["all_words_overrides_state"] = None
            print(f"[AI Studio] Using {len(active_words)} pre-transcribed/rectified words from transcript cache (Skipping Whisper!)", flush=True)

        video_dur = _get_video_duration(video_path)
        if async_mode is None:
            # Auto-enable async background mode for videos > 45s to avoid Claude Desktop 240s timeout
            is_async = (video_dur > 45.0)
        else:
            is_async = bool(async_mode)

        if is_async:
            job_id = f"render_{uuid.uuid4().hex[:8]}"
            with RENDER_LOCK:
                RENDER_JOBS[job_id] = {
                    "job_id": job_id,
                    "status": "QUEUED",
                    "progress": 0,
                    "message": "Initializing background video rendering...",
                    "output_path": None,
                    "error": None,
                    "created_at": time.time(),
                    "video_path": video_path,
                    "video_duration": round(video_dur, 2)
                }

            def _bg_render():
                with RENDER_LOCK:
                    if job_id in RENDER_JOBS:
                        RENDER_JOBS[job_id]["status"] = "RUNNING"
                        RENDER_JOBS[job_id]["message"] = "Processing video with Whisper and graphics engine..."

                def _progress_cb(pct, msg=""):
                    with RENDER_LOCK:
                        if job_id in RENDER_JOBS:
                            if isinstance(pct, (int, float)):
                                RENDER_JOBS[job_id]["progress"] = max(0, min(100, int(pct * 100)))
                            if msg:
                                RENDER_JOBS[job_id]["message"] = str(msg)

                params["progress"] = _progress_cb
                try:
                    with contextlib.redirect_stdout(sys.stderr):
                        output = render_video_gui(**params)
                    with RENDER_LOCK:
                        if job_id in RENDER_JOBS:
                            RENDER_JOBS[job_id]["status"] = "COMPLETED"
                            RENDER_JOBS[job_id]["progress"] = 100
                            RENDER_JOBS[job_id]["message"] = "Rendering completed successfully."
                            RENDER_JOBS[job_id]["output_path"] = os.path.abspath(output)
                except Exception as exc:
                    import traceback
                    with RENDER_LOCK:
                        if job_id in RENDER_JOBS:
                            RENDER_JOBS[job_id]["status"] = "FAILED"
                            RENDER_JOBS[job_id]["error"] = f"{str(exc)}\n{traceback.format_exc()}"
                            RENDER_JOBS[job_id]["message"] = f"Render failed: {str(exc)}"

            thread = threading.Thread(target=_bg_render, daemon=True)
            thread.start()

            return json.dumps({
                "status": "STARTED",
                "job_id": job_id,
                "video_path": video_path,
                "video_duration_seconds": round(video_dur, 2),
                "message": f"Video rendering started in background (Job ID: '{job_id}') to prevent Claude Desktop client timeout. Call get_render_status('{job_id}') to monitor progress and receive the final video path when complete.",
                "next_step": f"Call get_render_status('{job_id}') to check status and wait for completion."
            }, indent=2)

        # Synchronous execution for short clips or explicit async_mode=False
        with contextlib.redirect_stdout(sys.stderr):
            output = render_video_gui(**params)
        return os.path.abspath(output)
    except Exception as e:
        import traceback
        return f"Error rendering captions: {str(e)}\n{traceback.format_exc()}"

@mcp.tool()
def get_render_status(job_id: Optional[str] = None) -> str:
    """
    Checks the real-time status and progress of a background video rendering job.
    If job_id is omitted, checks the status of the most recently submitted render job.
    
    Args:
        job_id: The job ID returned by render_captions_video (e.g. 'render_a1b2c3d4').
        
    Returns:
        JSON string with job_id, status ("RUNNING" | "COMPLETED" | "FAILED"),
        progress (0-100), message, and output_path (when complete).
    """
    with RENDER_LOCK:
        if not RENDER_JOBS:
            return json.dumps({"status": "NOT_FOUND", "message": "No background render jobs found."}, indent=2)
        if not job_id:
            target_id = max(RENDER_JOBS.keys(), key=lambda k: RENDER_JOBS[k].get("created_at", 0))
            job = RENDER_JOBS[target_id]
        elif job_id in RENDER_JOBS:
            job = RENDER_JOBS[job_id]
        else:
            return json.dumps({"status": "NOT_FOUND", "job_id": job_id, "message": f"Job ID '{job_id}' not found."}, indent=2)

        elapsed = round(time.time() - job.get("created_at", time.time()), 1)
        res = {
            "job_id": job.get("job_id"),
            "status": job.get("status"),
            "progress": job.get("progress", 0),
            "message": job.get("message", ""),
            "output_path": job.get("output_path"),
            "elapsed_seconds": elapsed
        }
        if job.get("error"):
            res["error"] = job.get("error")
        return json.dumps(res, indent=2)

@mcp.tool()
def list_available_presets() -> List[dict]:
    """
    Lists all available ZetaCap presets installed in the system.
    Returns a list of dictionaries with 'name', 'filename', 'path', and 'format' (.zeta or .json).
    """
    from project.services.preset_choreographer import get_installed_presets
    return get_installed_presets()

@mcp.tool()
def set_multi_preset_choreography(
    cadence_mode: str = "Natural Sentence Cadence (Recommended)",
    preset_paths: Optional[List[str]] = None,
    lock_alignment: bool = True,
    unified_zoom: bool = True
) -> str:
    """
    Sets up multi-preset rotation choreography pool for ZetaCap live UI and rendering.
    
    Args:
        cadence_mode: "Natural Sentence Cadence (Recommended)", "Alternating (Every Chunk)", "Alternating (Every 2 Chunks)", "Single Preset (Disabled)"
        preset_paths: List of preset names, filenames (e.g. ['clean.json', 'white in red.zeta']), or absolute paths.
        lock_alignment: Whether to keep baseline positioning locked across alternating presets.
        unified_zoom: Whether to harmonize auto-zoom motion across presets.
    """
    from project.services.preset_choreographer import resolve_preset_path
    resolved = []
    if preset_paths:
        for p in preset_paths:
            rp = resolve_preset_path(p)
            if rp and rp not in resolved:
                resolved.append(rp)
                
    mode = cadence_mode
    if resolved and len(resolved) >= 2 and mode == "Single Preset (Disabled)":
        mode = "Natural Sentence Cadence (Recommended)"
        
    res = _write_mcp_sync("set_multi_preset_choreography", {
        "multi_preset_mode": mode,
        "multi_preset_pool": resolved,
        "multi_preset_lock_alignment": lock_alignment,
        "multi_preset_unified_zoom": unified_zoom
    })
    if res is True:
        preset_names = [os.path.basename(p) for p in resolved] if resolved else []
        return f"Choreography pool configured with {len(resolved)} presets ({', '.join(preset_names)}) in mode '{mode}'."
    return f"Failed to configure choreography: {res}"

if __name__ == "__main__":
    # Start the FastMCP server with stdio transport
    mcp.run()
