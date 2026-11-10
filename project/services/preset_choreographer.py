import os
import json
import zipfile
import tempfile
import uuid
import random

def resolve_preset_path(source):
    """
    Intelligently resolves any preset name, partial name, filename, or path
    to an absolute file path on disk (.zeta or .json).
    """
    if not source or not isinstance(source, str):
        return None
    source = source.strip()
    if os.path.isfile(source):
        return os.path.abspath(source)
        
    from ..core.config import config
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs = [
        config.PRESETS_DIR,
        project_root,
        os.path.join(project_root, "presets")
    ]
    
    # 1. Exact or standard extensions match
    for d in search_dirs:
        if not d or not os.path.exists(d):
            continue
        cands = [
            os.path.join(d, source),
            os.path.join(d, os.path.basename(source)),
            os.path.join(d, f"{source}.zeta"),
            os.path.join(d, f"{source}.json"),
            os.path.join(d, f"{os.path.basename(source)}.zeta"),
            os.path.join(d, f"{os.path.basename(source)}.json")
        ]
        for c in cands:
            if os.path.isfile(c):
                return os.path.abspath(c)
                
    # 2. Fuzzy / normalized matching
    norm = source.lower().replace(".zeta", "").replace(".json", "").replace(" ", "").replace("_", "").replace("-", "")
    for d in search_dirs:
        if not d or not os.path.exists(d):
            continue
        try:
            for f in os.listdir(d):
                if f.endswith((".zeta", ".json")):
                    if f in ("mcp_sync.json", "test_mcp.json", "project.json", "package.json"):
                        continue
                    fn_norm = f.lower().replace(".zeta", "").replace(".json", "").replace(" ", "").replace("_", "").replace("-", "")
                    if norm in fn_norm or fn_norm in norm:
                        return os.path.abspath(os.path.join(d, f))
        except Exception:
            pass
            
    return None

def get_installed_presets():
    """
    Returns a list of dictionaries describing all installed presets.
    """
    from ..core.config import config
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    search_dirs = [
        config.PRESETS_DIR,
        os.path.join(project_root, "presets"),
        project_root
    ]
    
    seen = set()
    presets_list = []
    
    for d in search_dirs:
        if not d or not os.path.exists(d):
            continue
        try:
            for f in os.listdir(d):
                if f.endswith((".zeta", ".json")):
                    if f in ("mcp_sync.json", "test_mcp.json", "project.json", "package.json"):
                        continue
                    full_path = os.path.abspath(os.path.join(d, f))
                    if full_path in seen:
                        continue
                    seen.add(full_path)
                    name = os.path.splitext(f)[0].strip()
                    fmt = ".zeta" if f.endswith(".zeta") else ".json"
                    presets_list.append({
                        "name": name,
                        "filename": f,
                        "path": full_path,
                        "format": fmt
                    })
        except Exception:
            pass
            
    return presets_list

def load_preset_data(preset_source):
    """
    Loads and normalizes preset settings from a .zeta, .json file path, or dictionary.
    Returns a settings dictionary.
    """
    if isinstance(preset_source, dict):
        return preset_source.get("settings", preset_source)
        
    if not isinstance(preset_source, str) or not preset_source.strip():
        return {}
        
    resolved_path = resolve_preset_path(preset_source)
    if not resolved_path or not os.path.exists(resolved_path):
        return {}
            
    try:
        if resolved_path.endswith(".json"):
            with open(resolved_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("settings", data)
        elif resolved_path.endswith(".zeta"):
            extract_dir = os.path.join(tempfile.gettempdir(), f"zetacap_choreography_{uuid.uuid4().hex[:8]}")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(resolved_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)
            project_json = os.path.join(extract_dir, "project.json")
            if os.path.exists(project_json):
                with open(project_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                s = data.get("settings", data)
                # Map relative asset paths
                for key in ["font_upload", "font_file_2", "custom_roto_font_file", "sfx_upload_file"]:
                    val = s.get(key)
                    if val and isinstance(val, str) and val.startswith("assets/"):
                        s[key] = os.path.join(extract_dir, val)
                return s
    except Exception as e:
        print(f"[PresetChoreographer] Error loading preset from {preset_source} ({resolved_path}): {e}")
        
    return {}


class PresetChoreographer:
    """
    Intelligent Choreography Engine for Multi-Preset alternating, cadence detection,
    style arbitration, and unified camera motion.
    """
    
    MODES = [
        "Single Preset (Disabled)",
        "Alternating (Every Chunk)",
        "Natural Sentence Cadence (Recommended)"
    ]
    
    def __init__(self, preset_pool=None, mode="Single Preset (Disabled)", lock_alignment=True, unified_zoom=True, master_defaults=None):
        self.lock_alignment = lock_alignment
        self.unified_zoom = unified_zoom
        self.master_defaults = master_defaults or {}
        
        # Load all presets in the pool
        self.presets = []
        if preset_pool:
            for p in preset_pool:
                p_data = load_preset_data(p)
                if p_data:
                    self.presets.append(p_data)
                    
        # Active whenever 1 or more valid presets are loaded in the pool
        self.is_active = (len(self.presets) >= 1)
        
        if self.is_active and len(self.presets) >= 2 and (not mode or mode == "Single Preset (Disabled)"):
            self.mode = "Natural Sentence Cadence (Recommended)"
        else:
            self.mode = mode if mode in self.MODES else "Single Preset (Disabled)"
            
        self.chunk_assignments = []

    def plan_schedule(self, chunks):
        """
        Assigns a preset index (0 to len(presets)-1) to each chunk based on the cadence strategy.
        chunks: List of chunk lists (each chunk containing word dicts with 'text', 'start', 'end').
        """
        self.chunk_assignments = []
        if not chunks:
            return self.chunk_assignments
            
        n_presets = len(self.presets)
        if not self.is_active or n_presets <= 1 or self.mode == "Single Preset (Disabled)":
            self.chunk_assignments = [0] * len(chunks)
            return self.chunk_assignments
            
        num_chunks = len(chunks)
        
        if self.mode == "Alternating (Every Chunk)":
            self.chunk_assignments = [i % n_presets for i in range(num_chunks)]
            
        elif self.mode == "Alternating (Every 2 Chunks)":
            self.chunk_assignments = [(i // 2) % n_presets for i in range(num_chunks)]
            
        elif self.mode == "Natural Sentence Cadence (Recommended)":
            curr_idx = 0
            for idx, chunk in enumerate(chunks):
                self.chunk_assignments.append(curr_idx)
                
                # Check if this chunk ends a sentence or clause
                chunk_text = " ".join(w.get("text", "").strip() for w in chunk)
                ends_sentence = any(chunk_text.endswith(p) for p in [".", "!", "?", "—", "..."])
                
                # Check pause to next chunk if available
                has_long_pause = False
                if idx < num_chunks - 1:
                    curr_end = chunk[-1].get("end", 0.0)
                    next_start = chunks[idx+1][0].get("start", 0.0)
                    if (next_start - curr_end) >= 0.45:
                        has_long_pause = True
                        
                if ends_sentence or has_long_pause:
                    curr_idx = (curr_idx + 1) % n_presets
                    
        else:
            self.chunk_assignments = [0] * num_chunks
            
        return self.chunk_assignments

    def get_style_for_chunk(self, chunk_idx, fallback_settings=None):
        """
        Resolves the comprehensive style parameters for a specific chunk index.
        Merges preset attributes with lock-alignment rules and fallback settings.
        """
        fb = fallback_settings or self.master_defaults or {}
        
        if not self.is_active or not self.presets:
            return fb
            
        # Get assigned preset index
        if chunk_idx < len(self.chunk_assignments):
            p_idx = self.chunk_assignments[chunk_idx]
        else:
            p_idx = (chunk_idx % len(self.presets)) if self.presets else 0
            
        preset = self.presets[p_idx % len(self.presets)]
        
        # Merge preset with fallback
        style = dict(fb)
        
        # Specific style keys to pull from the assigned preset
        style_keys = [
            "font_preset_dropdown", "font_upload", "multi_font_mode", "font_preset_choice_2", "font_file_2",
            "font_size_slider", "bottom_font_size_slider",
            "show_shadow", "shadow_depth", "shadow_step_x", "shadow_step_y",
            "sheen_3d_scope", "gloss_intensity",
            "t1_top", "t1_mid", "t1_bot", "t1_shadow",
            "t2_top", "t2_mid", "t2_bot", "t2_shadow",
            "show_glow", "t1_glow", "t2_glow", "glow_strength",
            "bg_box_enable", "bg_box_color",
            "random_brush_highlights", "text_animation_style",
            "lines_mode_dropdown", "line_spacing_scale",
            "max_words_slider", "max_chars_slider"
        ]
        
        for k in style_keys:
            if k in preset and preset[k] is not None:
                style[k] = preset[k]
                
        # Alignment and safe area
        if not self.lock_alignment:
            for k in ["vertical_alignment", "pos_offset_x", "pos_offset_y"]:
                if k in preset and preset[k] is not None:
                    style[k] = preset[k]
                    
        return style
