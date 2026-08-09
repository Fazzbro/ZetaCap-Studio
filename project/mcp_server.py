from mcp.server.fastmcp import FastMCP
from typing import List, Optional
import os
import sys

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from project.services.compile_service import compile_video_sync
from project.services.backend_renderer import render_video_gui
from project.services.silence_service import get_volume_segments

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
    zoom_transition_style: str = "🌊 Lush S-Curve Cinematic Glide"
) -> str:
    """
    Updates the live animation and layout settings in ZetaCap UI.
    Use zoom_transition_style="🌊 Lush S-Curve Cinematic Glide" for S-curve zoom, 
    or "⚡ Fast Snappy CapCut Punch" for CapCut-style zoom.
    pos_offset_y adjusts the vertical position of the captions.
    DO NOT ask follow up questions about rendering. Just execute silently.
    """
    res = _write_mcp_sync("update_animation_settings", {
        "pos_offset_y": pos_offset_y,
        "enable_auto_zoom": enable_auto_zoom,
        "zoom_transition_style": zoom_transition_style
    })
    if res is True:
        return "Live sync command sent to ZetaCap. The UI will update instantly."
    return f"Failed to send sync command: {res}"

@mcp.tool()
def update_sfx_settings(
    enable_sfx: bool,
    sfx_preset_choice: Optional[str] = None
) -> str:
    """
    Updates the live SFX settings in the ZetaCap UI.
    """
    res = _write_mcp_sync("update_sfx_settings", {
        "enable_sfx": enable_sfx,
        "sfx_preset_choice": sfx_preset_choice
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
    audio_aspect_ratio: str = "16:9 Landscape (YouTube)"
) -> str:
    """
    Automatically transcribes the video using Whisper, applies animated typography styles, 
    and renders the final captioned video.
    
    Args:
        video_path: Absolute path to the compiled/trimmed video to be captioned.
        output_mode: Defines the output. Options: 
                     "Burn directly into Video (Hardsubs)",
                     "Export as Transparent MOV (Captions Only)",
                     "Export as Greenscreen MP4 (Captions Only)"
                     
    Returns:
        The absolute path to the final rendered video.
    """
    import contextlib
    import json
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
            "progress": None
        }

        if preset_path and os.path.exists(preset_path):
            with open(preset_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            s = data.get("settings", data)
            
            # Resolve font path relative to preset directory if not absolute
            if "font_upload" in s and s["font_upload"]:
                font_upload_val = s["font_upload"]
                if not os.path.isabs(font_upload_val):
                    preset_dir = os.path.dirname(preset_path)
                    resolved_font = os.path.join(preset_dir, font_upload_val)
                    if os.path.exists(resolved_font):
                        s["font_upload"] = resolved_font
                        
            if "font_file_2" in s and s["font_file_2"]:
                font_file_2_val = s["font_file_2"]
                if not os.path.isabs(font_file_2_val):
                    preset_dir = os.path.dirname(preset_path)
                    resolved_font2 = os.path.join(preset_dir, font_file_2_val)
                    if os.path.exists(resolved_font2):
                        s["font_file_2"] = resolved_font2

            import base64
            import tempfile
            embedded_fonts = data.get("embedded_fonts", {})
            if embedded_fonts:
                temp_dir = os.path.join(tempfile.gettempdir(), "zetacap_fonts")
                os.makedirs(temp_dir, exist_ok=True)
                for font_name, b64_data in embedded_fonts.items():
                    font_path = os.path.join(temp_dir, font_name)
                    try:
                        with open(font_path, "wb") as font_file:
                            font_file.write(base64.b64decode(b64_data))
                        
                        for key in ["font_upload", "font_file_2"]:
                            if s.get(key) == font_name:
                                s[key] = font_path
                    except Exception as fe:
                        print(f"Warning: Could not extract font {font_name}: {fe}")

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
                    if param_val is not None or target_key not in ["words_table", "whisper_words_state", "all_words_overrides_state"]:
                        params[target_key] = param_val
                    
        with contextlib.redirect_stdout(sys.stderr):
            output = render_video_gui(**params)
        return os.path.abspath(output)
    except Exception as e:
        import traceback
        return f"Error rendering captions: {str(e)}
{traceback.format_exc()}"


if __name__ == "__main__":
    # Start the FastMCP server with stdio transport
    mcp.run()
