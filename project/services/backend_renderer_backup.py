import sys
import asyncio
import warnings

# Suppress noisy third-party library deprecation warnings (e.g. Starlette HTTP_422_UNPROCESSABLE_ENTITY deprecation)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")
try:
    from starlette.deprecation import StarletteDeprecationWarning
    warnings.filterwarnings("ignore", category=StarletteDeprecationWarning)
except ImportError:
    pass

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 1. WINDOWS SELECTOR EVENT LOOP POLICY FIX (Required at top-level)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    import whisper_timestamped as whisper
except ImportError:
    try:
        import whisper
    except ImportError:
        whisper = None
from moviepy import VideoFileClip, AudioFileClip, ColorClip, TextClip, CompositeVideoClip, ImageClip
import numpy as np
import torch
import os
import json
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import cv2

from ..core.config import config, get_bundled_path

OPENCV_MODEL_DIR = config.OPENCV_MODEL_DIR
WHISPER_MODEL_DIR = config.WHISPER_MODEL_DIR
YUNET_MODEL_PATH = config.YUNET_MODEL_PATH
HAAR_MODEL_PATH = config.HAAR_MODEL_PATH

# ==========================================
# 2. STUDIO-GRADE GRAPHICS & ANIMATION ENGINE
# ==========================================

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

import moviepy.video.VideoClip as vc_module

# Monkeypatch MoviePy compose_mask to fix ValueError on negative off-screen positions
_original_compose_mask = vc_module.VideoClip.compose_mask

def _safe_compose_mask(self, background_mask, t):
    ct = t - self.start
    clip_mask = self.get_frame(ct).astype("float")
    bg_h, bg_w = background_mask.shape
    clip_h, clip_w = clip_mask.shape
    
    pos = self.pos(ct)
    from moviepy.video.VideoClip import compute_position
    pos = compute_position((clip_w, clip_h), (bg_w, bg_h), pos, self.relative_pos)
    
    x_start = int(max(pos[0], 0))
    x_end = int(max(0, min(pos[0] + clip_w, bg_w)))  # FIXED: added max(0, ...)
    y_start = int(max(pos[1], 0))
    y_end = int(max(0, min(pos[1] + clip_h, bg_h)))  # FIXED: added max(0, ...)
    
    if x_start >= x_end or y_start >= y_end:
        return background_mask
        
    return _original_compose_mask(self, background_mask, t)

vc_module.VideoClip.compose_mask = _safe_compose_mask

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

def make_gradient_text(text, font, font_size, color_top, color_mid, color_bottom, gloss_intensity=1.2, margin_x=20, margin_y=50):
    """Generates premium studio text with intense dual-layer specular gloss, smooth Hermite 3-stop gradient, and inner bevel shading."""
    base = TextClip(text=text, font=font, font_size=font_size, color='white', margin=(margin_x, margin_y))
    mask = base.mask.get_frame(0)
    h, w = mask.shape
    grad = np.zeros((h, w, 3), dtype=np.uint8)
    
    for y in range(h):
        effective_y = y - margin_y
        effective_h = max(h - (margin_y * 2), 1)
        ratio = max(0.0, min(1.0, effective_y / effective_h))
        
        # 1. Base 3-Stop Color Blend via Smooth Hermite Easing
        if ratio <= 0.5:
            t = ratio * 2.0
            smooth = t * t * (3.0 - 2.0 * t)  # Cubic Hermite S-Curve
            r = color_top[0] * (1.0 - smooth) + color_mid[0] * smooth
            g = color_top[1] * (1.0 - smooth) + color_mid[1] * smooth
            b = color_top[2] * (1.0 - smooth) + color_mid[2] * smooth
        else:
            t = (ratio - 0.5) * 2.0
            smooth = t * t * (3.0 - 2.0 * t)
            r = color_mid[0] * (1.0 - smooth) + color_bottom[0] * smooth
            g = color_mid[1] * (1.0 - smooth) + color_bottom[1] * smooth
            b = color_mid[2] * (1.0 - smooth) + color_bottom[2] * smooth
            
        # 2. Premium Studio Glass & Metallic Specular Gloss (Controlled by gloss_intensity)
        g_val = float(gloss_intensity)
        if g_val > 0:
            # Top Sharp Bevel & Glass Rim Highlight (Top 22%)
            if ratio < 0.22:
                rim_shine = ((1.0 - (ratio / 0.22)) ** 1.2) * 0.95 * g_val
                r = r + (255.0 - r) * min(1.0, rim_shine)
                g = g + (255.0 - g) * min(1.0, rim_shine)
                b = b + (255.0 - b) * min(1.0, rim_shine)
                
            # Acrylic / Metallic Mid-Body Dome Reflection (Upper 50%)
            if ratio < 0.50:
                body_shine = ((1.0 - (ratio / 0.50)) ** 1.4) * 0.45 * g_val
                r = r + (255.0 - r) * min(1.0, body_shine)
                g = g + (255.0 - g) * min(1.0, body_shine)
                b = b + (255.0 - b) * min(1.0, body_shine)
                
            # Metallic Specular Horizon Band across ratio 0.38 - 0.47 (Chrome/Metallic sheen sweep)
            horizon_dist = abs(ratio - 0.42)
            if horizon_dist < 0.07:
                horizon_intensity = ((1.0 - (horizon_dist / 0.07)) ** 1.8) * 0.65 * g_val
                r = r + (255.0 - r) * min(1.0, horizon_intensity)
                g = g + (255.0 - g) * min(1.0, horizon_intensity)
                b = b + (255.0 - b) * min(1.0, horizon_intensity)
            
        # 3. Inner Bevel Shading (Physical 3D Molded Depth near bottom edge)
        if ratio > 0.80:
            bevel_dark = 1.0 - (((ratio - 0.80) / 0.20) * 0.28)
            r = r * bevel_dark
            g = g * bevel_dark
            b = b * bevel_dark
            
        grad[y, :, :] = [
            int(max(0, min(255, r))),
            int(max(0, min(255, g))),
            int(max(0, min(255, b)))
        ]
        
    try:
        mask_clip = ImageClip(mask, is_mask=True)
    except TypeError:
        mask_clip = ImageClip(mask, ismask=True)
        
    return ImageClip(grad).with_mask(mask_clip)

def get_solid_3d_extrusion(text, font, font_size, hex_color, depth=9, step_x=1, step_y=1, margin_x=20, margin_y=50):
    """Generates sculpted 3D block extrusion with ambient occlusion gradient plus a subtle contact drop shadow."""
    layers = []
    h_c = hex_color.lstrip('#')
    r, g, b = tuple(int(h_c[i:i+2], 16) for i in (0, 2, 4))
    
    # Contact Ambient Shadow Layer at bottom back
    contact_shadow = TextClip(text=text, font=font, font_size=font_size, color="#111116", margin=(margin_x, margin_y))
    layers.append((contact_shadow, depth * step_x + 3 * step_x, depth * step_y + 4 * step_y))
    
    # Ambient Occlusion Extrusion Stack
    for i in range(depth, 0, -1):
        ao_factor = max(0.18, 1.0 - ((i / max(1, depth)) ** 1.2) * 0.72)
        c = f"#{int(r*ao_factor):02x}{int(g*ao_factor):02x}{int(b*ao_factor):02x}"
        t = TextClip(text=text, font=font, font_size=font_size, color=c, margin=(margin_x, margin_y))
        layers.append((t, i * step_x, i * step_y))
    return layers

def hex_to_rgb(hex_color):
    """Translates hex string representations to RGB tuples."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def alpha_composite_onto(canvas, clip, pos_x, pos_y):
    """Composites a single MoviePy clip frame onto a numpy RGB canvas."""
    rgb = clip.get_frame(0)
    mask = clip.mask.get_frame(0) if clip.mask else np.ones(rgb.shape[:2])
    ch, cw, _ = canvas.shape
    h, w, _ = rgb.shape

    x1 = max(0, pos_x)
    y1 = max(0, pos_y)
    x2 = min(cw, pos_x + w)
    y2 = min(ch, pos_y + h)

    if x2 <= x1 or y2 <= y1:
        return

    cx1 = x1 - pos_x
    cy1 = y1 - pos_y
    cx2 = cx1 + (x2 - x1)
    cy2 = cy1 + (y2 - y1)

    sub_rgb = rgb[cy1:cy2, cx1:cx2]
    sub_alpha = mask[cy1:cy2, cx1:cx2, None]

    canvas[y1:y2, x1:x2] = (
        sub_rgb * sub_alpha + canvas[y1:y2, x1:x2] * (1.0 - sub_alpha)
    ).astype(np.uint8)

def get_resolved_font_path(font_source=None, custom_upload_file=None):
    """Resolves font preset choice or custom uploaded file to an absolute .ttf/.otf file path."""
    if custom_upload_file and os.path.exists(str(custom_upload_file)):
        # If user explicitly uploaded a file and/or selected Custom Upload
        if font_source is None or "Custom Uploaded" in str(font_source) or not str(font_source).strip():
            return str(custom_upload_file)
            
    import sys
    if getattr(sys, 'frozen', False):
        script_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    choice = str(font_source or "").strip()
    
    if "Sans-Serif Bold" in choice or not choice:
        system_candidates = [
            r"C:\Windows\Fonts\ariblk.ttf",        # Windows Arial Black
            r"C:\Windows\Fonts\impact.ttf",        # Windows Impact
            r"C:\Windows\Fonts\arialbd.ttf",       # Windows Arial Bold
            r"C:\Windows\Fonts\segoeuib.ttf",      # Windows Segoe UI Bold
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux DejaVu Sans Bold
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Linux Liberation Sans Bold
            "DejaVuSans-Bold",
            "LiberationSans-Bold",
            "Arial-Bold",
            "Arial-BoldMT",
            "Arial"
        ]
        for candidate in system_candidates:
            if os.path.exists(candidate):
                return candidate
        p_def = os.path.join(script_dir, "Poppins-Bold.ttf")
        if os.path.exists(p_def): return p_def
        return "Arial-Bold"
    elif "Helvetica Bold" in choice and not "Oblique" in choice:
        p = os.path.join(script_dir, "Helvetica-Bold.ttf")
        if os.path.exists(p): return p
    elif "Helvetica Oblique" in choice:
        p = os.path.join(script_dir, "Helvetica-Oblique.ttf")
        if os.path.exists(p): return p
    elif "SF Pro Display" in choice:
        p = os.path.join(script_dir, "SFPRODISPLAYMEDIUM.OTF")
        if os.path.exists(p): return p
    elif "Fraunces" in choice:
        p = os.path.join(script_dir, "Fraunces_72pt_Soft-BoldItalic.ttf")
        if os.path.exists(p): return p
    elif "Poppins Medium" in choice:
        p = os.path.join(script_dir, "Poppins-Medium.ttf")
        if os.path.exists(p): return p
    elif "Poppins Bold" in choice or "Poppins" in choice:
        p = os.path.join(script_dir, "Poppins-Bold.ttf")
        if os.path.exists(p): return p
    elif "Custom Uploaded" in choice and custom_upload_file and os.path.exists(str(custom_upload_file)):
        return str(custom_upload_file)
        
    # If font_source is already a raw file path that exists on disk:
    if font_source and os.path.exists(str(font_source)):
        return str(font_source)
    if custom_upload_file and os.path.exists(str(custom_upload_file)):
        return str(custom_upload_file)
        
    p_def = os.path.join(script_dir, "Poppins-Bold.ttf")
    if os.path.exists(p_def):
        return p_def
    if os.path.exists("Poppins-Bold.ttf"):
        return "Poppins-Bold.ttf"
    return None

def resolve_sans_serif_bold_font(font_source=None, custom_upload_file=None):
    """Resolves font to user uploaded custom font or selected preset font path."""
    resolved = get_resolved_font_path(font_source, custom_upload_file)
    if resolved and os.path.exists(resolved):
        return resolved
        
    system_candidates = [
        r"C:\Windows\Fonts\ariblk.ttf",        # Windows Arial Black
        r"C:\Windows\Fonts\impact.ttf",        # Windows Impact
        r"C:\Windows\Fonts\arialbd.ttf",       # Windows Arial Bold
        r"C:\Windows\Fonts\segoeuib.ttf",      # Windows Segoe UI Bold
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux DejaVu Sans Bold
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Linux Liberation Sans Bold
        "DejaVuSans-Bold",
        "LiberationSans-Bold",
        "Arial-Bold",
        "Arial-BoldMT",
        "Arial"
    ]
    for candidate in system_candidates:
        if os.path.exists(candidate):
            return candidate
            
    return "Arial-Bold"

def resolve_pil_font(font_source=None, font_size=135, custom_upload_file=None):
    """Loads heavy ultra-bold sans-serif typeface or selected preset font for PIL rendering."""
    resolved = get_resolved_font_path(font_source, custom_upload_file)
    candidates = []
    if resolved and os.path.exists(resolved):
        candidates.append(resolved)
        
    import sys
    if getattr(sys, 'frozen', False):
        script_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    candidates.extend([
        r"C:\Windows\Fonts\ariblk.ttf",       # Arial Black
        r"C:\Windows\Fonts\impact.ttf",       # Impact
        r"C:\Windows\Fonts\arialbd.ttf",      # Arial Bold
        os.path.join(script_dir, "Poppins-Bold.ttf"),
        "Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ])
    for c in candidates:
        if os.path.exists(c):
            try:
                f = ImageFont.truetype(c, int(font_size))
                print(f"[DEBUG] resolve_pil_font SUCCESS: {c}", flush=True)
                return f
            except Exception as e:
                print(f"[DEBUG] resolve_pil_font FAILED for {c}: {e}", flush=True)
                pass
    print("[DEBUG] resolve_pil_font FALLBACK to load_default()", flush=True)
    return ImageFont.load_default()

def create_tight_text_mask(text, font, tracking=-4, pad=40, outline_only=False, stroke_width=3):
    """Draws character-by-character text mask with extremely tight kerning & tracking."""
    if not text:
        return Image.new("L", (10, 10), 0)
        
    total_w = 0
    max_h = 0
    char_boxes = []
    for i, ch in enumerate(text):
        bbox = font.getbbox(ch)
        adv = font.getlength(ch)
        char_boxes.append((ch, bbox, adv))
        if i == len(text) - 1:
            total_w += max(bbox[2], adv)
        else:
            total_w += adv + tracking
        max_h = max(max_h, bbox[3] - bbox[1])
        
    canvas_w = int(math.ceil(total_w)) + pad * 2
    canvas_h = int(math.ceil(max_h)) + pad * 2
    
    mask = Image.new("L", (canvas_w, canvas_h), 0)
    draw = ImageDraw.Draw(mask)
    
    cursor_x = pad
    sample_bbox = font.getbbox("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    baseline_y = pad - sample_bbox[1]
    
    for i, (ch, bbox, adv) in enumerate(char_boxes):
        if outline_only:
            draw.text((cursor_x, baseline_y), ch, font=font, fill=0, stroke_width=int(stroke_width), stroke_fill=255)
        else:
            draw.text((cursor_x, baseline_y), ch, font=font, fill=255)
        if i < len(char_boxes) - 1:
            cursor_x += adv + tracking
            
    bbox_actual = mask.getbbox()
    if not bbox_actual:
        return mask
    left, top, right, bottom = bbox_actual
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(mask.width, right + pad)
    bottom = min(mask.height, bottom + pad)
    return mask.crop((left, top, right, bottom))

def build_top_layer_extruded_plastic(
    text, font, tracking=-4, pad=40,
    top_hex="#FFD56B", mid_hex="#FF7300", bot_hex="#E53900", shadow_hex="#1A0000",
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    outline_only=False, stroke_width=3, show_glow=True, glow_hex="#FF7300", glow_strength=1.0
):
    """
    Layer 1: Top Text Appearance ("Stop posting")
    - 3-Stop Hermite vertical linear gradient (top_hex -> mid_hex -> bot_hex)
    - Dynamic Specular Gloss, Bevel Highlight & Metallic Horizon Sheen controlled by gloss_intensity
    - Sculpted 3D Solid Extrusion Stack controlled by shadow_depth & shadow_hex
    - Dynamic Outer Ambient Glow controlled by show_glow & glow_hex
    """
    text_mask = create_tight_text_mask(text, font, tracking=tracking, pad=pad, outline_only=outline_only, stroke_width=stroke_width)
    w, h = text_mask.size
    
    top_rgb = hex_to_rgb(top_hex)
    mid_rgb = hex_to_rgb(mid_hex)
    bot_rgb = hex_to_rgb(bot_hex)
    shadow_rgb = hex_to_rgb(shadow_hex)
    
    base_grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    grad_pixels = base_grad.load()
    mask_pixels = text_mask.load()
    
    bbox = text_mask.getbbox()
    t_top = bbox[1] if bbox else 0
    t_bot = bbox[3] if bbox else h
    t_h = max(1, t_bot - t_top)
    
    g_val = float(gloss_intensity)
    
    for y in range(h):
        ratio = max(0.0, min(1.0, (y - t_top) / t_h))
        # 3-Stop Hermite S-Curve Gradient
        if ratio <= 0.5:
            t = ratio * 2.0
            smooth = t * t * (3.0 - 2.0 * t)
            r = top_rgb[0] * (1.0 - smooth) + mid_rgb[0] * smooth
            g = top_rgb[1] * (1.0 - smooth) + mid_rgb[1] * smooth
            b = top_rgb[2] * (1.0 - smooth) + mid_rgb[2] * smooth
        else:
            t = (ratio - 0.5) * 2.0
            smooth = t * t * (3.0 - 2.0 * t)
            r = mid_rgb[0] * (1.0 - smooth) + bot_rgb[0] * smooth
            g = mid_rgb[1] * (1.0 - smooth) + bot_rgb[1] * smooth
            b = mid_rgb[2] * (1.0 - smooth) + bot_rgb[2] * smooth
            
        # Specular Gloss & Metallic Sheen (Controlled by gloss_intensity)
        if g_val > 0 and not outline_only:
            # 1. Top Specular Glass Rim (Upper 22%)
            if ratio < 0.22:
                rim = ((1.0 - (ratio / 0.22)) ** 1.2) * 0.95 * g_val
                r = r + (255.0 - r) * min(1.0, rim)
                g = g + (255.0 - g) * min(1.0, rim)
                b = b + (255.0 - b) * min(1.0, rim)
                
            # 2. Polished Studio Glass / Acrylic Body Reflection (Upper 50%)
            if ratio < 0.50:
                body = ((1.0 - (ratio / 0.50)) ** 1.4) * 0.45 * g_val
                r = r + (255.0 - r) * min(1.0, body)
                g = g + (255.0 - g) * min(1.0, body)
                b = b + (255.0 - b) * min(1.0, body)
                
            # 3. Ultra Metallic Shine Horizon Band across ratio ~ 0.38 to 0.47
            horizon_dist = abs(ratio - 0.42)
            if horizon_dist < 0.07:
                horizon_shine = ((1.0 - (horizon_dist / 0.07)) ** 1.8) * 0.65 * g_val
                r = r + (255.0 - r) * min(1.0, horizon_shine)
                g = g + (255.0 - g) * min(1.0, horizon_shine)
                b = b + (255.0 - b) * min(1.0, horizon_shine)
                
        # Inner Bevel Shading near bottom edge
        if ratio > 0.82 and not outline_only:
            bevel = ((ratio - 0.82) / 0.18) * 0.4 * max(1.0, g_val)
            r = r * (1.0 - bevel)
            g = g * (1.0 - bevel)
            b = b * (1.0 - bevel)
            
        r_int = int(max(0, min(255, r)))
        g_int = int(max(0, min(255, g)))
        b_int = int(max(0, min(255, b)))
        for x in range(w):
            alpha = mask_pixels[x, y]
            if alpha > 0:
                grad_pixels[x, y] = (r_int, g_int, b_int, alpha)
    
    if outline_only:
        return base_grad
                
    # Inner Shine Bevel along top inner edges (Scales directly with gloss_intensity)
    offset_y = max(2, int(font.size * 0.028))
    offset_mask = ImageChops.offset(text_mask, 0, offset_y)
    draw_off = ImageDraw.Draw(offset_mask)
    draw_off.rectangle([0, 0, w, offset_y], fill=0)
    
    inner_top_edge = ImageChops.subtract(text_mask, offset_mask)
    bevel_alpha = min(255, int(150 * max(1.0, g_val)))
    shine_layer = Image.new("RGBA", (w, h), (255, 255, 255, bevel_alpha))
    shine_layer.putalpha(inner_top_edge)
    
    composite = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    
    # Solid 3D Extrusion Stack
    if show_shadow and int(shadow_depth) > 0:
        depth = int(shadow_depth)
        s_x = int(shadow_step_x)
        s_y = int(shadow_step_y)
        for i in range(depth, 0, -1):
            ao_factor = max(0.25, 1.0 - ((i / max(1, depth)) ** 1.2) * 0.65)
            r_ao = int(shadow_rgb[0] * ao_factor)
            g_ao = int(shadow_rgb[1] * ao_factor)
            b_ao = int(shadow_rgb[2] * ao_factor)
            layer_i = Image.new("RGBA", (w, h), (r_ao, g_ao, b_ao, 255))
            layer_i.putalpha(text_mask)
            composite.alpha_composite(layer_i, (i * s_x, i * s_y))
            
    # Outer Ambient Glow / Halo
    if show_glow and glow_hex and str(glow_hex).strip().lower() != "none":
        if show_glow:
            from PIL import ImageFilter
            if float(glow_strength) <= 0: glow_strength = 0.001
            radius_val = max(1, int(font.size * 0.06 * float(glow_strength)))
            glow_mask = text_mask.filter(ImageFilter.GaussianBlur(radius=radius_val))
            glow_layer = Image.new("RGBA", (w, h), glow_hex)
            glow_layer.putalpha(glow_mask)
            passes = max(1, int(float(glow_strength) * 2.0) if float(glow_strength) > 1.0 else 1)
            for _ in range(passes):
                composite.alpha_composite(glow_layer)
    
    composite.alpha_composite(base_grad, (0, 0))
    composite.alpha_composite(shine_layer, (0, 0))
    return composite

def build_bottom_layer_stark_white(
    text, font, tracking=-4, pad=40,
    top_hex="#FFFFFF", mid_hex="#CCCCCC", bot_hex="#AAAAAA", shadow_hex="#0A0A0A",
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    outline_only=False, stroke_width=3, show_glow=False, glow_hex="#FFFFFF", glow_strength=1.0
):
    """
    Layer 2: Bottom Text Appearance
    - Now correctly supports the full 3D extruded plastic, gloss, and glow effects
      so that 'glow and things' apply identically to both lines.
    """
    return build_top_layer_extruded_plastic(
        text, font, tracking=tracking, pad=pad,
        top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
        gloss_intensity=gloss_intensity, show_shadow=show_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        outline_only=outline_only, stroke_width=stroke_width,
        show_glow=show_glow, glow_hex=glow_hex, glow_strength=glow_strength
    )

def render_stacked_captions_png(
    text_top, text_bottom, font_source=None, font_upload=None, font_source_2=None, font_upload_2=None, font_size=135, bottom_font_size=135, tracking=-5, leading=6,
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    t1_top_hex="#FFD56B", t1_mid_hex="#FF7300", t1_bot_hex="#E53900", t1_shadow_hex="#1A0000",
    t2_top_hex="#FFFFFF", t2_mid_hex="#CCCCCC", t2_bot_hex="#AAAAAA", t2_shadow_hex="#0A0A0A",
    line_spacing_scale=0.82, sheen_3d_scope="Both Lines (Top + Bottom - Default)",
    outline_only=False, stroke_width=3, show_glow=True, t1_glow_hex="#FF7300", t2_glow_hex="None", glow_strength=1.0,
    bg_box_enable=False, bg_box_color="#F5F2DA",
    nudge_x_1=0, nudge_y_1=0, nudge_x_2=0, nudge_y_2=0
):
    """Creates a cohesive, stacked block of text with minimal line height and full 3D metallic gloss."""
    if show_shadow and shadow_depth <= 0:
        shadow_depth = 5
        
    font_1 = resolve_pil_font(font_source, font_size, custom_upload_file=font_upload)
    if font_source_2 and font_source_2 != "Same as Primary Font (Single Font Mode)":
        font_2 = resolve_pil_font(font_source_2, bottom_font_size, custom_upload_file=font_upload_2)
        if font_2 is None:
            font_2 = resolve_pil_font(font_source, bottom_font_size, custom_upload_file=font_upload)
    else:
        font_2 = resolve_pil_font(font_source, bottom_font_size, custom_upload_file=font_upload)
        
    l1_shadow = show_shadow
    l1_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else 0.0
    
    l2_shadow = show_shadow
    l2_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else 0.0
        
    eff_pad = int(45 + max(0, (float(glow_strength) * 40))) if show_glow else 35
    
    img_top = build_top_layer_extruded_plastic(
        text_top, font_1, tracking=tracking, pad=eff_pad,
        top_hex=t1_top_hex, mid_hex=t1_mid_hex, bot_hex=t1_bot_hex, shadow_hex=t1_shadow_hex,
        gloss_intensity=l1_gloss, show_shadow=l1_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        outline_only=outline_only, stroke_width=stroke_width,
        show_glow=show_glow, glow_hex=t1_glow_hex, glow_strength=glow_strength
    )
    img_bot = build_bottom_layer_stark_white(
        text_bottom, font_2, tracking=tracking, pad=eff_pad,
        top_hex=t2_top_hex, mid_hex=t2_mid_hex, bot_hex=t2_bot_hex, shadow_hex=t2_shadow_hex,
        gloss_intensity=l2_gloss, show_shadow=l2_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        outline_only=outline_only, stroke_width=stroke_width,
        show_glow=show_glow, glow_hex=t2_glow_hex, glow_strength=glow_strength
    )
    
    bbox_top = img_top.getbbox()
    bbox_bot = img_bot.getbbox()
    w_top, h_top = img_top.size
    w_bot, h_bot = img_bot.size
    
    final_w = max(w_top, w_bot) + 40
    
    x_top = (final_w - w_top) // 2 + int(nudge_x_1)
    y_top = 30 + int(nudge_y_1)
    x_bot = (final_w - w_bot) // 2 + int(nudge_x_2)
    
    if text_bottom:
        line_gap = int(font_size * 0.82 * float(line_spacing_scale))
        y_bot = 30 + line_gap + int(nudge_y_2)
    else:
        y_bot = y_top + h_top
        
    # Ensure canvas is large enough for positive nudges
    final_w = max(final_w, x_top + w_top + 40, x_bot + w_bot + 40)
    final_h = max(y_top + h_top, y_bot + h_bot) + 30
    
    # Handle negative nudges by shifting everything positive
    min_x = min(x_top, x_bot) if text_bottom else x_top
    min_y = min(y_top, y_bot) if text_bottom else y_top
    if min_x < 0:
        x_top -= min_x
        x_bot -= min_x
        final_w -= min_x
    if min_y < 0:
        y_top -= min_y
        y_bot -= min_y
        final_h -= min_y
    stacked = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    
    if bg_box_enable:
        draw_bg = ImageDraw.Draw(stacked)
        rect_color = bg_box_color
        if rect_color.startswith('#') and len(rect_color) == 7:
            rect_color = rect_color + "FF" # Add alpha
        padding_x, padding_y = 40, 20
        box_x1 = min(x_top, x_bot) if text_bottom else x_top
        box_x2 = max(x_top + w_top, x_bot + w_bot) if text_bottom else x_top + w_top
        
        # Calculate bounding box for background
        draw_bg.rectangle(
            [box_x1 - padding_x, y_top - padding_y, box_x2 + padding_x, max(y_top + h_top, y_bot + h_bot) + padding_y],
            fill=rect_color
        )
        
    stacked.alpha_composite(img_top, (x_top, y_top))
    if text_bottom:
        stacked.alpha_composite(img_bot, (x_bot, y_bot))
        
    return stacked

def render_caption_layer_image_clip(
    text, font_source=None, font_upload=None, font_size=135, is_top_layer=True, tracking=-4,
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    top_hex="#FFD56B", mid_hex="#FF7300", bot_hex="#E53900", shadow_hex="#1A0000",
    sheen_3d_scope="Both Lines (Top + Bottom - Default)",
    outline_only=False, stroke_width=3, show_glow=True, glow_hex="#FF7300", glow_strength=1.0,
    highlight_word=None
):
    """Converts a PIL rendered transparent caption layer into a MoviePy ImageClip with proper RGBA mask."""
    font = resolve_pil_font(font_source, font_size, custom_upload_file=font_upload)
    if is_top_layer:
        eff_shadow = show_shadow
        eff_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else 0.0
        pil_img = build_top_layer_extruded_plastic(
            text, font, tracking=tracking, pad=35,
            top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
            gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
            shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
            outline_only=outline_only, stroke_width=stroke_width,
            show_glow=show_glow, glow_hex=glow_hex, glow_strength=glow_strength
        )
    else:
        eff_shadow = show_shadow
        eff_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else 0.0
        pil_img = build_bottom_layer_stark_white(
            text, font, tracking=tracking, pad=35,
            top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
            gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
            shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
            outline_only=outline_only, stroke_width=stroke_width,
            show_glow=show_glow, glow_hex=glow_hex, glow_strength=glow_strength
        )
        
    if highlight_word and highlight_word in text and not outline_only:
        try:
            # Generate highlighted version
            hl_hex_top = "#32CD32"
            hl_hex_mid = "#228B22"
            hl_hex_bot = "#006400"
            if is_top_layer:
                hl_img = build_top_layer_extruded_plastic(
                    highlight_word, font, tracking=tracking, pad=35,
                    top_hex=hl_hex_top, mid_hex=hl_hex_mid, bot_hex=hl_hex_bot, shadow_hex=shadow_hex,
                    gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
                    shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
                    outline_only=outline_only, stroke_width=stroke_width,
                    show_glow=show_glow, glow_hex=hl_hex_top, glow_strength=glow_strength
                )
            else:
                hl_img = build_bottom_layer_stark_white(
                    highlight_word, font, tracking=tracking, pad=35,
                    top_hex=hl_hex_top, mid_hex=hl_hex_mid, bot_hex=hl_hex_bot, shadow_hex=shadow_hex,
                    gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
                    shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
                    outline_only=outline_only, stroke_width=stroke_width,
                    show_glow=show_glow, glow_hex=hl_hex_top, glow_strength=glow_strength
                )
            
            # Calculate x_offset using string width
            prefix = text[:text.find(highlight_word)]
            x_offset = 0
            for ch in prefix:
                x_offset += font.getlength(ch) + tracking
            x_offset = int(x_offset)
            
            # Load and composite brush
            import os
            brush_path = os.path.join("assets", "brush_green.png")
            if os.path.exists(brush_path):
                brush = Image.open(brush_path).convert("RGBA")
                brush_w = max(10, hl_img.width - 70) # Adjust for padding
                brush_h = max(5, int(brush.height * (brush_w / brush.width)))
                brush = brush.resize((brush_w, brush_h), Image.Resampling.LANCZOS)
                
                # Brush positioning
                bbox = font.getbbox("A")
                baseline_y = 35 + (bbox[3] - bbox[1]) # pad + height
                brush_y = baseline_y - (brush_h // 2) + int(font.size * 0.15)
                
                pil_img.alpha_composite(brush, (x_offset + 35, brush_y))
            
            # Composite green text over white text
            pil_img.alpha_composite(hl_img, (x_offset, 0))
        except Exception as e:
            print(f"Error drawing brush highlight: {e}")

    arr = np.array(pil_img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0
    try:
        mask_clip = ImageClip(alpha, is_mask=True)
    except TypeError:
        mask_clip = ImageClip(alpha, ismask=True)
    return ImageClip(rgb).with_mask(mask_clip)

def generate_style_preview_gui(
    video_file,
    words_table,
    whisper_words_state,
    all_words_overrides_state,
    preview_timestamp,
    font_preset_choice,
    font_file, 
    multi_font_mode,
    font_preset_choice_2,
    font_file_2,
    font_size, 
    bottom_font_size,
    show_shadow, 
    shadow_depth, 
    shadow_step_x, 
    shadow_step_y,
    sheen_3d_scope,
    gloss_intensity,
    t1_top_hex, 
    t1_mid_hex, 
    t1_bot_hex, 
    t1_shadow_hex, 
    t2_top_hex, 
    t2_mid_hex, 
    t2_bot_hex, 
    t2_shadow_hex,
    show_glow=True,
    t1_glow_hex="#FF7300",
    t2_glow_hex="None",
    glow_strength=1.0,
    bg_box_enable=False,
    bg_box_color="#F5F2DA",
    max_words_per_chunk=2,
    max_chars_per_line=28,
    lines_per_caption="2 Lines (Top + Bottom Stack)",
    line_spacing_scale=0.82,
    vertical_alignment="Lower Third (60% Height - Default)",
    pos_offset_x=0,
    pos_offset_y=0,
    random_brush_highlights=False,
    rotoscope_enable=False,
    rotoscope_style="Text Behind Speaker (Standard Full Rotoscope - Default)",
    rotoscope_outline_width=3,
    custom_roto_text="",
    custom_roto_font="Impact",
    custom_roto_font_size=150,
    custom_roto_color="#FFFFFF",
    custom_roto_show_glow=False,
    custom_roto_glow_color="#FF7300",
    custom_roto_glow_strength=1.0,
    custom_roto_pos_x=0,
    custom_roto_pos_y=0,
    rotoscope_start_sec=0.0,
    rotoscope_end_sec=3.0,
    rotoscope_downsample="0.25 (Fastest / Recommended - 60 FPS)"
):
    """Generates an instant high-res PNG style preview respecting all 3D Shiny Glow & Specular Gloss parameters and split modes."""
    canvas_w, canvas_h = 1080, 1920
    bg = Image.new("RGBA", (canvas_w, canvas_h), (15, 23, 42, 255))
    preview_src_frame = None
    
    if video_file and os.path.exists(str(video_file)):
        try:
            from moviepy import VideoFileClip
            clip = VideoFileClip(str(video_file))
            target_time = min(float(preview_timestamp), clip.duration - 0.1) if clip.duration > 0 else 0.0
            first_frame_arr = clip.get_frame(target_time)
            clip.close()
            preview_src_frame = first_frame_arr
            bg_pil = Image.fromarray(first_frame_arr).convert("RGBA")
            canvas_w, canvas_h = bg_pil.size
            bg = bg_pil
        except Exception as e:
            print(f"Warning: Could not extract first frame from video ({video_file}): {e}")
            
    FONT_SIZE = int(font_size)
    
    sample_words = ["stop", "posting", "disconnected", "videos", "because", "nobody", "watches", "them"]
    chunk_size = max(1, int(max_words_per_chunk))
    chunk = []
    found_chunk = []
    found_chunk_data = []
    
    if words_table and whisper_words_state:
        words_list = []
        for row in words_table:
            try:
                idx = int(row[0])
                if 0 <= idx < len(whisper_words_state):
                    orig = whisper_words_state[idx]
                    text_val = str(row[1]).strip() if (len(row) > 1 and row[1] is not None) else orig["text"]
                    words_list.append({
                        "start": orig["start"],
                        "end": orig["end"],
                        "text": text_val,
                        "x_nudge": float(row[3]) if (len(row) > 3 and row[3] is not None and str(row[3]).replace('-','').replace('.','').isdigit()) else 0.0,
                        "y_nudge": float(row[4]) if (len(row) > 4 and row[4] is not None and str(row[4]).replace('-','').replace('.','').isdigit()) else 0.0
                    })
            except Exception:
                continue
                
        if words_list:
            found_chunk = None
            found_chunk_data = None
            for i in range(0, len(words_list), chunk_size):
                c = words_list[i:i+chunk_size]
                c_start = c[0]["start"]
                c_end = c[-1]["end"]
                # Match chunks that overlap with the preview timestamp, adding a 0.1s padding.
                # If timestamp is exactly on the boundary, prefer the chunk starting at this time.
                if c_start - 0.01 <= preview_timestamp <= (c_end + 0.1):
                    if found_chunk is None or preview_timestamp >= (c_start - 0.01):
                        found_chunk = [w["text"] for w in c]
                        found_chunk_data = c
            
            if not found_chunk and preview_timestamp == 0.0:
                found_chunk = [w["text"] for w in words_list[:chunk_size]]
                found_chunk_data = words_list[:chunk_size]
            elif not found_chunk:
                found_chunk = []
                found_chunk_data = []
                
            chunk = found_chunk
    
    if not chunk and (not words_table or len(words_table) == 0):
        chunk = sample_words[:chunk_size]    
    def format_caption_text(s):
        s = s.strip()
        if not s:
            return ""
        return s[0].upper() + s[1:]
        
    char_limit = max(10, int(max_chars_per_line))
    is_single_line = ("single" in str(lines_per_caption).lower() or "1 line" in str(lines_per_caption).lower())
    
    word1_words = []
    word2_words = []
    if is_single_line:
        text1 = format_caption_text(" ".join(chunk))
        text2 = ""
        word1_words = found_chunk_data
    else:
        if len(chunk) <= 1:
            text1 = format_caption_text(chunk[0]) if chunk else "Stop"
            text2 = ""
            word1_words = found_chunk_data
        else:
            best_mid = len(chunk) // 2
            min_diff = 999
            for mid in range(1, len(chunk)):
                l1 = " ".join(chunk[:mid])
                l2 = " ".join(chunk[mid:])
                if len(l1) > char_limit and mid > 1:
                    continue
                diff = abs(len(l1) - len(l2))
                if diff < min_diff:
                    min_diff = diff
                    best_mid = mid
            text1 = format_caption_text(" ".join(chunk[:best_mid]))
            text2 = format_caption_text(" ".join(chunk[best_mid:]))
            if found_chunk_data and len(found_chunk_data) == len(chunk):
                word1_words = found_chunk_data[:best_mid]
                word2_words = found_chunk_data[best_mid:]
            
    if "Single Font" in str(multi_font_mode) or font_preset_choice_2 == "Same as Primary Font (Single Font Mode)":
        preview_font_source_2 = font_preset_choice
        preview_font_upload_2 = font_file
    else:
        preview_font_source_2 = font_preset_choice_2
        preview_font_upload_2 = font_file_2
    
    nudge_x_1 = 0
    nudge_y_1 = 0
    nudge_x_2 = 0
    nudge_y_2 = 0
    if words_table and whisper_words_state and 'word1_words' in locals():
        nudge_x_1 = sum(w.get("x_nudge", 0.0) for w in word1_words)
        nudge_y_1 = sum(w.get("y_nudge", 0.0) for w in word1_words)
    if words_table and whisper_words_state and 'word2_words' in locals():
        nudge_x_2 = sum(w.get("x_nudge", 0.0) for w in word2_words)
        nudge_y_2 = sum(w.get("y_nudge", 0.0) for w in word2_words)

    stacked_img = render_stacked_captions_png(
        text1, text2, font_source=font_preset_choice, font_upload=font_file, font_source_2=preview_font_source_2, font_upload_2=preview_font_upload_2, font_size=FONT_SIZE, bottom_font_size=int(bottom_font_size), tracking=-int(FONT_SIZE * 0.04), leading=int(FONT_SIZE * 0.045),
        gloss_intensity=gloss_intensity, show_shadow=show_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        t1_top_hex=t1_top_hex, t1_mid_hex=t1_mid_hex, t1_bot_hex=t1_bot_hex, t1_shadow_hex=t1_shadow_hex,
        t2_top_hex=t2_top_hex, t2_mid_hex=t2_mid_hex, t2_bot_hex=t2_bot_hex, t2_shadow_hex=t2_shadow_hex,
        line_spacing_scale=float(line_spacing_scale), sheen_3d_scope=sheen_3d_scope,
        show_glow=show_glow, t1_glow_hex=t1_glow_hex, t2_glow_hex=t2_glow_hex, glow_strength=glow_strength,
        bg_box_enable=bg_box_enable, bg_box_color=bg_box_color,
        nudge_x_1=nudge_x_1, nudge_y_1=nudge_y_1, nudge_x_2=nudge_x_2, nudge_y_2=nudge_y_2
    )
    
    x = (canvas_w - stacked_img.width) // 2 + int(pos_offset_x)
    if "Center" in str(vertical_alignment):
        base_y_ratio = 0.50
    elif "Upper Third" in str(vertical_alignment):
        base_y_ratio = 0.28
    elif "Bottom Edge" in str(vertical_alignment):
        base_y_ratio = 0.82
    else:
        base_y_ratio = 0.60
    y = int(canvas_h * base_y_ratio) - (stacked_img.height // 2) + int(pos_offset_y)
    
    # Determine if current normal captions have a manual override to be behind the speaker
    normal_captions_behind = False
    if 'word1_words' in locals():
        if any("Text Behind Speaker" in str(w.get("rotoscope_override", "")) for w in word1_words):
            normal_captions_behind = True
    if 'word2_words' in locals():
        if any("Text Behind Speaker" in str(w.get("rotoscope_override", "")) for w in word2_words):
            normal_captions_behind = True
            
    # 1. Draw custom rotoscope text if enabled and active in this timeframe
    if rotoscope_enable and custom_roto_text and str(custom_roto_text).strip() and float(rotoscope_start_sec) <= float(preview_timestamp) <= float(rotoscope_end_sec):
        custom_roto_clip = render_caption_layer_image_clip(
            custom_roto_text, font_source=custom_roto_font, font_upload=None, font_size=int(custom_roto_font_size), is_top_layer=True, tracking=-int(custom_roto_font_size * 0.04),
            gloss_intensity=0.0, show_shadow=False, shadow_depth=0,
            shadow_step_x=0, shadow_step_y=0,
            top_hex=custom_roto_color, mid_hex=custom_roto_color, bot_hex=custom_roto_color, shadow_hex="#000000",
            sheen_3d_scope=100.0, show_glow=custom_roto_show_glow, glow_hex=custom_roto_glow_color, glow_strength=float(custom_roto_glow_strength)
        )
        custom_frame = custom_roto_clip.get_frame(0)
        try:
            custom_mask = custom_roto_clip.mask.get_frame(0)
            rgba_frame = np.dstack((custom_frame, (custom_mask * 255).astype(np.uint8)))
            custom_pil = Image.fromarray(rgba_frame, "RGBA")
        except Exception:
            custom_pil = Image.fromarray(custom_frame).convert("RGBA")
        c_pos_x = (canvas_w - custom_pil.width) // 2 + int(custom_roto_pos_x)
        c_pos_y = (canvas_h - custom_pil.height) // 2 + int(custom_roto_pos_y)
        bg.alpha_composite(custom_pil, (c_pos_x, c_pos_y))
        
    # 2. Draw normal captions ONLY if they are overridden to be behind
    if normal_captions_behind:
        bg.alpha_composite(stacked_img, (x, y))
    
    # 3. Apply RVM Mask (Speaker over background) if any rotoscope is active
    if rotoscope_enable and preview_src_frame is not None and float(rotoscope_start_sec) <= float(preview_timestamp) <= float(rotoscope_end_sec):
        try:
            ds_ratio = 0.25
            if "0.50" in str(rotoscope_downsample):
                ds_ratio = 0.50
            elif "0.125" in str(rotoscope_downsample):
                ds_ratio = 0.125
            fgr, pha, _ = get_rvm_mask(preview_src_frame, downsample_ratio=ds_ratio)
            if fgr is not None and pha is not None:
                fgr_pil = Image.fromarray(fgr.astype(np.uint8)).convert("RGBA")
                pha_pil = Image.fromarray((pha[:, :, 0] * 255.0).astype(np.uint8)).convert("L")
                bg = Image.composite(fgr_pil, bg, pha_pil)
        except Exception as e_roto_prev:
            print(f"[Warning] Rotoscope preview overlay failed: {e_roto_prev}", flush=True)

    # 4. Draw normal captions in FRONT by default (if not overridden)
    if not normal_captions_behind:
        bg.alpha_composite(stacked_img, (x, y))
    
    preview_path = os.path.join(config.OUTPUT_DIR, "live_style_preview.png")
    bg.convert("RGB").save(preview_path, "PNG")
    return preview_path

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


# ==========================================
# 2.5. FACE IDENTIFICATION & OCCASIONAL AUTO-ZOOM ENGINE
# ==========================================

def detect_face_centers_for_intervals(video_path, intervals, model_choice, canvas_w, canvas_h):
    """
    Scans representative frames for each caption block/interval using YuNet or Haar Cascade from D:\\ai_models.
    Returns list of intervals enriched with 'face_cx', 'face_cy', and 'has_face'.
    """
    if not os.path.exists(video_path):
        return intervals

    detector_type = "yunet" if "YuNet" in str(model_choice) and os.path.exists(YUNET_MODEL_PATH) else "haar"
    yunet_detector = None
    haar_cascade = None

    if detector_type == "yunet":
        try:
            yunet_detector = cv2.FaceDetectorYN.create(
                model=YUNET_MODEL_PATH,
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
        if os.path.exists(HAAR_MODEL_PATH):
            haar_cascade = cv2.CascadeClassifier(HAAR_MODEL_PATH)
        else:
            print(f"[Warning] Haar cascade model not found at {HAAR_MODEL_PATH}. Using center fallback.", flush=True)

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
                        active_idx = max(0, idx - 1)
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


# ==========================================
# 3. VIDEO & TRANSCRIPTION PROCESSING PIPELINE
# ==========================================

PAGE_SIZE = 15

def get_page_info_html(total_filtered, current_page, page_size=PAGE_SIZE, search_only=False, is_query_empty=True):
    if search_only and is_query_empty:
        return f"<div style='color: #38BDF8; font-weight: 600; text-align: center; padding: 8px;'>⚡ Search-Only Mode Active: Type a word or ID in the search box above to display and edit matching words! ({total_filtered} total words loaded)</div>"
    if total_filtered <= 0:
        return "<div style='color: #94A3B8; font-weight: 600; text-align: center; padding: 8px;'>No words found.</div>"
    max_pages = max(1, (total_filtered + page_size - 1) // page_size)
    start_idx = current_page * page_size + 1
    end_idx = min(total_filtered, (current_page + 1) * page_size)
    return f"<div style='color: #4ADE80; font-weight: 600; text-align: center; padding: 8px;'>Showing words {start_idx} to {end_idx} of {total_filtered} total words (Page {current_page + 1} of {max_pages})</div>"

def sync_table_edits_to_master(words_table_data, master_state):
    if master_state is None or not isinstance(master_state, list):
        master_state = []
    if not words_table_data or not isinstance(words_table_data, (list, tuple)):
        return master_state
    for row in words_table_data:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            try:
                idx = int(row[0])
                if 0 <= idx < len(master_state):
                    # Keep full 7 columns
                    master_state[idx] = list(row)[:7]
            except Exception:
                continue
    return master_state

def get_paginated_slice(master_state, current_page=0, search_query="", page_size=PAGE_SIZE, search_only=False):
    if not master_state or not isinstance(master_state, list):
        return [], get_page_info_html(0, 0, page_size, search_only, True), 0
    
    query = str(search_query).strip().lower()
    if search_only and not query:
        info_html = get_page_info_html(len(master_state), 0, page_size, True, True)
        return [], info_html, 0
        
    if query:
        filtered = [r for r in master_state if query in str(r[0]).lower() or query in str(r[1]).lower()]
    else:
        filtered = master_state
        
    total_filtered = len(filtered)
    max_pages = max(1, (total_filtered + page_size - 1) // page_size)
    current_page = max(0, min(max_pages - 1, int(current_page)))
    
    start_idx = current_page * page_size
    end_idx = start_idx + page_size
    slice_rows = filtered[start_idx:end_idx]
    info_html = get_page_info_html(total_filtered, current_page, page_size, search_only, bool(not query))
    return slice_rows, info_html, current_page

def change_page_gui(words_table_data, master_state, current_page, search_query, direction, search_only):
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    query = str(search_query).strip().lower()
    if query:
        filtered = [r for r in master_state if query in str(r[0]).lower() or query in str(r[1]).lower()]
    else:
        filtered = master_state
    max_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
    new_page = max(0, min(max_pages - 1, int(current_page) + int(direction)))
    slice_rows, info_html, new_page = get_paginated_slice(master_state, new_page, search_query, PAGE_SIZE, search_only)
    return slice_rows, master_state, new_page, info_html

def filter_words_gui(words_table_data, master_state, search_query, search_only):
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    slice_rows, info_html, new_page = get_paginated_slice(master_state, 0, search_query, PAGE_SIZE, search_only)
    return slice_rows, master_state, 0, search_query, info_html

def clear_search_gui(words_table_data, master_state, search_only):
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    slice_rows, info_html, new_page = get_paginated_slice(master_state, 0, "", PAGE_SIZE, search_only)
    return slice_rows, master_state, 0, "", info_html

def sync_table_change_gui(words_table_data, master_state):
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    return master_state

def on_table_select_gui(evt, words_table_data, master_state):
    if words_table_data is None or len(words_table_data) == 0:
        return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", "<span style='color: #94A3B8;'>Select a word to inspect</span>"
    try:
        row_idx = int(evt.index[0])
        if 0 <= row_idx < len(words_table_data):
            row = words_table_data[row_idx]
            w_id = int(row[0]) if row[0] is not None else 0
            if master_state and 0 <= w_id < len(master_state):
                row = master_state[w_id]
            w_text = str(row[1]) if (len(row) > 1 and row[1] is not None) else ""
            w_font = str(row[2]) if (len(row) > 2 and row[2] is not None) else "None (Use Primary/Secondary)"
            w_xnudge = float(row[3]) if (len(row) > 3 and row[3] is not None and str(row[3]).replace('-','').replace('.','').isdigit()) else 0.0
            w_ynudge = float(row[4]) if (len(row) > 4 and row[4] is not None and str(row[4]).replace('-','').replace('.','').isdigit()) else 0.0
            w_color = str(row[5]) if (len(row) > 5 and row[5] is not None) else "None"
            w_roto = str(row[6]) if (len(row) > 6 and row[6] is not None) else "Normal (Default)"
            
            valid_fonts = [
                "None (Use Primary/Secondary)",
                "Sans-Serif Bold (System Default)",
                "Poppins Bold",
                "Poppins Medium",
                "Helvetica Bold",
                "Helvetica Oblique",
                "SF Pro Display Medium",
                "Fraunces",
                "Custom Uploaded (Use File Below)"
            ]
            if w_font not in valid_fonts:
                w_font = "None (Use Primary/Secondary)"
                
            valid_rotos = [
                "Normal (Default)",
                "Text Behind Speaker (Masked - Layer 2)",
                "Text In Front of Speaker (Unmasked - Layer 4)",
                "Outline Over Subject (Masking Effect)",
                "[DELETED] (Remove Word from Video)"
            ]
            if w_roto not in valid_rotos:
                w_roto = "Normal (Default)"
                
            color_enable = (w_color != "None" and w_color.startswith("#"))
            hex_color = w_color if color_enable else "#FFFFFF"
            status = f"<span style='color: #38BDF8; font-weight: 600;'>✔ Loaded Word ID {w_id} ('{w_text}') into surgical inspector!</span>"
            return w_id, w_text, w_font, w_roto, w_xnudge, w_ynudge, color_enable, hex_color, status
    except Exception as e:
        pass
    return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", "<span style='color: #94A3B8;'>Select a word to inspect</span>"

def on_inspector_id_change_gui(w_id, master_state):
    if master_state is None or len(master_state) == 0:
        return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", "<span style='color: #94A3B8;'>No words extracted yet</span>"
    try:
        w_id = int(w_id)
        if 0 <= w_id < len(master_state):
            row = master_state[w_id]
            w_text = str(row[1]) if (len(row) > 1 and row[1] is not None) else ""
            w_font = str(row[2]) if (len(row) > 2 and row[2] is not None) else "None (Use Primary/Secondary)"
            w_xnudge = float(row[3]) if (len(row) > 3 and row[3] is not None and str(row[3]).replace('-','').replace('.','').isdigit()) else 0.0
            w_ynudge = float(row[4]) if (len(row) > 4 and row[4] is not None and str(row[4]).replace('-','').replace('.','').isdigit()) else 0.0
            w_color = str(row[5]) if (len(row) > 5 and row[5] is not None) else "None"
            w_roto = str(row[6]) if (len(row) > 6 and row[6] is not None) else "Normal (Default)"
            
            valid_fonts = [
                "None (Use Primary/Secondary)",
                "Sans-Serif Bold (System Default)",
                "Poppins Bold",
                "Poppins Medium",
                "Helvetica Bold",
                "Helvetica Oblique",
                "SF Pro Display Medium",
                "Fraunces",
                "Custom Uploaded (Use File Below)"
            ]
            if w_font not in valid_fonts:
                w_font = "None (Use Primary/Secondary)"
                
            valid_rotos = [
                "Normal (Default)",
                "Text Behind Speaker (Masked - Layer 2)",
                "Text In Front of Speaker (Unmasked - Layer 4)",
                "Outline Over Subject (Masking Effect)",
                "[DELETED] (Remove Word from Video)"
            ]
            if w_roto not in valid_rotos:
                w_roto = "Normal (Default)"
                
            color_enable = (w_color != "None" and w_color.startswith("#"))
            hex_color = w_color if color_enable else "#FFFFFF"
            status = f"<span style='color: #38BDF8; font-weight: 600;'>✔ Loaded Word ID {w_id} ('{w_text}') into surgical inspector!</span>"
            return w_id, w_text, w_font, w_roto, w_xnudge, w_ynudge, color_enable, hex_color, status
    except Exception:
        pass
    return w_id, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", f"<span style='color: #F87171;'>Word ID {w_id} not found</span>"

def quick_search_word_gui(query, master_state):
    if not master_state or not isinstance(master_state, list):
        return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", "<span style='color: #F87171;'>No words extracted yet</span>"
    q = str(query).strip().lower()
    if not q:
        return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", "<span style='color: #94A3B8;'>Enter a word to find</span>"
    for row in master_state:
        if q in str(row[1]).lower() or q == str(row[0]):
            return on_inspector_id_change_gui(row[0], master_state)
    return 0, "", "None (Use Primary/Secondary)", "Normal (Default)", 0.0, 0.0, False, "#FFFFFF", f"<span style='color: #F87171;'>No word matching '{query}' found</span>"

def apply_word_override_gui(w_id, w_text, w_font, w_roto, w_xnudge, w_ynudge, color_enable, w_color, words_table_data, master_state, current_page, search_query, search_only):
    if master_state is None or len(master_state) == 0:
        return words_table_data, master_state, "<span style='color: #F87171;'>No master state available. Please extract words first.</span>"
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    try:
        w_id = int(w_id)
        if 0 <= w_id < len(master_state):
            c_val = str(w_color).strip() if (color_enable and w_color and str(w_color).startswith("#")) else "None"
            master_state[w_id] = [w_id, str(w_text).strip(), str(w_font), float(w_xnudge), float(w_ynudge), c_val, str(w_roto)]
            slice_rows, info_html, new_page = get_paginated_slice(master_state, current_page, search_query, PAGE_SIZE, search_only)
            status = f"<span style='color: #4ADE80; font-weight: 700;'>✔ Saved overrides for Word ID {w_id} ('{w_text}')!</span>"
            return slice_rows, master_state, status
    except Exception as e:
        status = f"<span style='color: #F87171;'>Error saving word: {e}</span>"
        return words_table_data, master_state, status
    return words_table_data, master_state, f"<span style='color: #F87171;'>Word ID {w_id} out of range</span>"

def delete_word_override_gui(w_id, words_table_data, master_state, current_page, search_query, search_only):
    if master_state is None or len(master_state) == 0:
        return words_table_data, master_state, "<span style='color: #F87171;'>No master state available.</span>"
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    try:
        w_id = int(w_id)
        if 0 <= w_id < len(master_state):
            master_state[w_id] = [w_id, "[DELETED]", "None (Use Primary/Secondary)", 0, 0, "None", "[DELETED] (Remove Word from Video)"]
            slice_rows, info_html, new_page = get_paginated_slice(master_state, current_page, search_query, PAGE_SIZE, search_only)
            status = f"<span style='color: #F87171; font-weight: 700;'>🗑️ Deleted Word ID {w_id} from video rendering!</span>"
            return slice_rows, master_state, status
    except Exception as e:
        return words_table_data, master_state, f"<span style='color: #F87171;'>Error deleting word: {e}</span>"
    return words_table_data, master_state, f"<span style='color: #F87171;'>Word ID {w_id} out of range</span>"

def reset_word_override_gui(w_id, whisper_words_state, words_table_data, master_state, current_page, search_query, search_only):
    if master_state is None or len(master_state) == 0:
        return words_table_data, master_state, "<span style='color: #F87171;'>No master state available.</span>"
    master_state = sync_table_edits_to_master(words_table_data, master_state)
    try:
        w_id = int(w_id)
        if 0 <= w_id < len(master_state):
            orig_text = master_state[w_id][1]
            if whisper_words_state and 0 <= w_id < len(whisper_words_state):
                orig_text = whisper_words_state[w_id].get("text", orig_text)
            master_state[w_id] = [w_id, orig_text, "None (Use Primary/Secondary)", 0, 0, "None", "Normal (Default)"]
            slice_rows, info_html, new_page = get_paginated_slice(master_state, current_page, search_query, PAGE_SIZE, search_only)
            status = f"<span style='color: #60A5FA; font-weight: 700;'>🔄 Reset Word ID {w_id} to default!</span>"
            return slice_rows, master_state, status
    except Exception as e:
        return words_table_data, master_state, f"<span style='color: #F87171;'>Error resetting: {e}</span>"
    return words_table_data, master_state, f"<span style='color: #F87171;'>Word ID {w_id} out of range</span>"

def transcribe_and_extract_words_gui(video_path, audio_path, audio_aspect_ratio, search_only=False, progress=None):
    has_video = video_path is not None and os.path.exists(str(video_path))
    has_audio = audio_path is not None and os.path.exists(str(audio_path))
    
    if not has_video and not has_audio:
        raise ValueError("Please upload either a Source Video (Option A) OR an Audio file (Option B) first!")
        
    if progress: progress(0.1, "Extracting Audio Track for Word Review...")
    print("\n[AI Studio] Step 1: Extracting audio for Interactive Word Editor...", flush=True)
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    temp_audio = os.path.join(output_dir, "temp_gui_audio_review.wav")
    media_clip = None
    
    if has_video:
        media_clip = VideoFileClip(video_path)
        if media_clip.audio is None:
            media_clip.close()
            raise ValueError("The uploaded video has no audio channel! Audio is required for transcription.")
        duration = media_clip.duration
        audio_clip = media_clip.audio
        try:
            audio_clip.write_audiofile(temp_audio, fps=16000, nbytes=2, codec='pcm_s16le', logger=None)
        except Exception as e:
            audio_clip.write_audiofile(temp_audio, logger=None)
    else:
        audio_clip = AudioFileClip(audio_path)
        try:
            audio_clip.write_audiofile(temp_audio, fps=16000, nbytes=2, codec='pcm_s16le', logger=None)
        except Exception as e:
            audio_clip.write_audiofile(temp_audio, logger=None)
            
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[AI Studio] Step 2: Transcribing audio with Whisper 'tiny' on {device.upper()}...", flush=True)
    if progress: progress(0.3, f"Transcribing words ({device.upper()})...")
    
    if device == "cuda":
        torch.cuda.empty_cache()
        
    model = whisper.load_model("tiny", device=device, download_root=WHISPER_MODEL_DIR)
    result = whisper.transcribe(model, temp_audio, language="en")
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
        
    if os.path.exists(temp_audio):
        try:
            os.remove(temp_audio)
        except Exception:
            pass
            
    if media_clip is not None:
        media_clip.close()
    if hasattr(audio_clip, 'close'):
        try:
            audio_clip.close()
        except Exception:
            pass
            
    segments = result.get("segments", [])
    all_words = []
    for seg in segments:
        for w in seg.get("words", []):
            all_words.append({
                "start": float(w["start"]),
                "end": float(w["end"]),
                "text": str(w["text"]).strip()
            })
            
    if not all_words:
        raise ValueError("No speech/words detected in the media.")
        
    # Full 7-column schema: [ID, Word Text, Font Override, X Nudge (px), Y Nudge (px), Color Override, Rotoscope Style Override]
    full_rows = [[idx, w["text"], "None (Use Primary/Secondary)", 0, 0, "None", "Normal (Default)"] for idx, w in enumerate(all_words)]
    print(f"[AI Studio] Extracted {len(all_words)} words with per-word styling/positioning/rotoscope columns! Enabling server-side pagination ({PAGE_SIZE} rows/page)...", flush=True)
    if progress: progress(1.0, "Words extracted! Review/Edit below, then click Render.")
    
    slice_rows, info_html, _ = get_paginated_slice(full_rows, 0, "", PAGE_SIZE, search_only)
    return slice_rows, all_words, full_rows, 0, "", info_html


def resolve_and_load_sfx_clip(sfx_preset, sfx_upload, volume=0.30):
    """Safely resolves the SFX preset or upload path, sanitizing chapters if necessary to avoid MoviePy IndexError."""
    sfx_path = None
    if sfx_upload and os.path.exists(str(sfx_upload)):
        sfx_path = str(sfx_upload)
    elif str(sfx_preset) != "None":
        sfx_path = None
        if "Pop (Tech)" in str(sfx_preset):
            sfx_path = get_bundled_path(os.path.join("assets", "mixkit-modern-technology-select-3124.wav"), r"d:\Python_Projects\captions\project\assets\mixkit-modern-technology-select-3124.wav")
        elif "Whoosh (Fast)" in str(sfx_preset):
            sfx_path = get_bundled_path(os.path.join("assets", "hi-sfx-aftereffects-videoediting-motiondesign-motiongraphi_49nxh1eV (1).mp3"), r"d:\Python_Projects\captions\project\assets\hi-sfx-aftereffects-videoediting-motiondesign-motiongraphi_49nxh1eV (1).mp3")
        elif "Click (Subtle)" in str(sfx_preset):
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


def render_video_gui(
    video_path, 
    audio_path,
    audio_aspect_ratio,
    words_table,
    whisper_words_state,
    all_words_overrides_state,
    font_preset_choice,
    font_file, 
    multi_font_mode,
    font_preset_choice_2,
    font_file_2,
    font_size, 
    bottom_font_size,
    show_shadow, 
shadow_depth,
    shadow_step_x,
    shadow_step_y,
    sheen_3d_scope,
    gloss_intensity,
    t1_top_hex, 
    t1_mid_hex, 
    t1_bot_hex, 
    t1_shadow_hex,
    t2_top_hex, 
    t2_mid_hex, 
    t2_bot_hex, 
    t2_shadow_hex,
    show_glow,
    t1_glow_hex,
    t2_glow_hex,
    glow_strength,
    bg_box_enable,
    bg_box_color,
    max_words_per_chunk,
    max_chars_per_line,
    lines_per_caption,
    line_spacing_scale,
    vertical_alignment,
    pos_offset_x,
    pos_offset_y,
    random_brush_highlights,
    output_mode,
    enable_auto_zoom,
    zoom_factor,
    zoom_frequency,
    zoom_transition_style,
    face_detector_model,
    min_cooldown_slider,
    zoom_hold_slider,
    enable_sfx=True,
    sfx_preset_choice="Mixkit Modern Technology Select (Default - 0.5s Clean Click)",
    sfx_upload_file=None,
    sfx_volume=0.30,
    sfx_trigger_mode="Every Caption Chunk Start (Default - Best Rhythm)",
    sfx_cooldown=0.35,
    rotoscope_enable=False,
    rotoscope_style="Text Behind Speaker (Standard Full Rotoscope - Default)",
    rotoscope_outline_width=3,
    custom_roto_text="",
    custom_roto_font="Impact",
    custom_roto_font_size=150,
    custom_roto_color="#FFFFFF",
    custom_roto_show_glow=False,
    custom_roto_glow_color="#FF7300",
    custom_roto_glow_strength=1.0,
    custom_roto_pos_x=0,
    custom_roto_pos_y=0,
    rotoscope_start_sec=0.0,
    rotoscope_end_sec=3.0,
    rotoscope_downsample="0.25 (Fastest / Recommended - 60 FPS)",
    progress=None
):
    has_video = video_path is not None and os.path.exists(str(video_path))
    has_audio = audio_path is not None and os.path.exists(str(audio_path))
    
    if not has_video and not has_audio:
        raise ValueError("Please upload either a Source Video (Option A) OR an Audio file (Option B)!")
        
    if all_words_overrides_state and isinstance(all_words_overrides_state, list) and len(all_words_overrides_state) > 0:
        effective_rows = sync_table_edits_to_master(words_table, all_words_overrides_state)
    else:
        effective_rows = words_table
        
    use_edited_words = (
        effective_rows is not None 
        and len(effective_rows) > 0 
        and whisper_words_state is not None 
        and len(whisper_words_state) > 0
    )
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    temp_audio = os.path.join(output_dir, "temp_gui_audio.wav")
    media_clip = None
    
    if use_edited_words:
        if progress: progress(0.1, "Loading Media & Preserving Edited Words...")
        print("\n[AI Studio] Step 1 & 2: Loading media dimensions & using edited word table from Interactive Word Editor...", flush=True)
        if has_video:
            media_clip = VideoFileClip(video_path)
            if media_clip.audio is None:
                media_clip.close()
                raise ValueError("The uploaded video has no audio channel!")
            canvas_w, canvas_h = media_clip.w, media_clip.h
            duration = media_clip.duration
            audio_clip = media_clip.audio
        else:
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            if "Vertical Shorts" in audio_aspect_ratio:
                canvas_w, canvas_h = 1080, 1920
            elif "Horizontal Landscape" in audio_aspect_ratio:
                canvas_w, canvas_h = 1920, 1080
            else:
                canvas_w, canvas_h = 1080, 1080
                
        words_list = []
        for row in effective_rows:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                try:
                    idx = int(row[0])
                except Exception:
                    continue
                if 0 <= idx < len(whisper_words_state):
                    orig = whisper_words_state[idx]
                    edited_text = str(row[1]).strip() if (len(row) > 1 and row[1] is not None) else orig["text"]
                    font_override = str(row[2]).strip() if (len(row) > 2 and row[2] is not None) else "None"
                    x_nudge = float(row[3]) if (len(row) > 3 and row[3] is not None and str(row[3]).replace('-','').replace('.','').isdigit()) else 0.0
                    y_nudge = float(row[4]) if (len(row) > 4 and row[4] is not None and str(row[4]).replace('-','').replace('.','').isdigit()) else 0.0
                    color_override = str(row[5]).strip() if (len(row) > 5 and row[5] is not None) else "None"
                    rotoscope_override = str(row[6]).strip() if (len(row) > 6 and row[6] is not None) else "Normal (Default)"
                    if edited_text:
                        words_list.append({
                            "start": orig["start"],
                            "end": orig["end"],
                            "text": edited_text,
                            "font_override": font_override,
                            "x_nudge": x_nudge,
                            "y_nudge": y_nudge,
                            "color_override": color_override,
                            "rotoscope_override": rotoscope_override
                        })
        segments = [{"words": words_list}] if words_list else []
    else:
        if progress: progress(0.1, "Loading Media & Extracting Audio Track...")
        print("\n[AI Studio] Step 1: Loading media track...", flush=True)
        
        if has_video:
            print("[AI Studio] Mode: Video Input detected. Extracting audio...", flush=True)
            media_clip = VideoFileClip(video_path)
            if media_clip.audio is None:
                media_clip.close()
                raise ValueError("The uploaded video has no audio channel! Audio is required for transcription.")
            canvas_w, canvas_h = media_clip.w, media_clip.h
            duration = media_clip.duration
            audio_clip = media_clip.audio
            try:
                audio_clip.write_audiofile(temp_audio, fps=16000, nbytes=2, codec='pcm_s16le', logger=None)
            except Exception as e:
                print(f"[Warning] PCM export failed ({e}). Fallback to standard write...", flush=True)
                audio_clip.write_audiofile(temp_audio, logger=None)
        else:
            print("[AI Studio] Mode: Direct Audio Upload (Option B) detected...", flush=True)
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration
            if "Vertical Shorts" in audio_aspect_ratio:
                canvas_w, canvas_h = 1080, 1920
            elif "Horizontal Landscape" in audio_aspect_ratio:
                canvas_w, canvas_h = 1920, 1080
            else:
                canvas_w, canvas_h = 1080, 1080
            try:
                audio_clip.write_audiofile(temp_audio, fps=16000, nbytes=2, codec='pcm_s16le', logger=None)
            except Exception as e:
                print(f"[Warning] PCM export failed ({e}). Fallback to standard write...", flush=True)
                audio_clip.write_audiofile(temp_audio, logger=None)
                
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[AI Studio] Step 2: Loading Whisper 'tiny' model on {device.upper()}...", flush=True)
        if progress: progress(0.2, f"Transcribing audio with whisper-timestamped ({device.upper()})...")
        
        if device == "cuda":
            torch.cuda.empty_cache()
            
        model = whisper.load_model("tiny", device=device, download_root=WHISPER_MODEL_DIR)
        result = whisper.transcribe(model, temp_audio, language="en")
        del model
        if device == "cuda":
            torch.cuda.empty_cache()
            
        if os.path.exists(temp_audio):
            try:
                os.remove(temp_audio)
            except Exception:
                pass
        
        segments = result.get("segments", [])
    if not segments:
        if media_clip is not None:
            media_clip.close()
        raise ValueError("No speech detected in the media. Please verify the audio level and try again.")
        
    if progress: progress(0.3, "Building Canvas & Typography Elements...")
    print(f"[AI Studio] Step 3: Setting up background layer for mode: {output_mode}...", flush=True)
    
    base_bg = None
    if "Burn directly" in str(output_mode):
        if not has_video or media_clip is None:
            if audio_clip is not None:
                audio_clip.close()
            if media_clip is not None:
                media_clip.close()
            raise ValueError("Burn-In mode requires Option A: Source Video upload! You uploaded an Audio file (Option B). Please choose Green Screen export.")
        base_bg = media_clip
    else:
        # Default: Chroma Key Green Screen
        base_bg = ColorClip(size=(canvas_w, canvas_h), color=(0, 255, 0), duration=duration)
        
    intervals = []
    chunk_size_check = max(1, int(max_words_per_chunk))
    for segment in segments:
        words_list = segment.get("words", [])
        if not words_list:
            continue
        for i in range(0, len(words_list), chunk_size_check):
            chunk = words_list[i:i+chunk_size_check]
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            if end_time > start_time:
                intervals.append({"start": start_time, "end": end_time})

    if enable_auto_zoom and has_video and base_bg is not None and "Burn directly" in str(output_mode) and intervals:
        print(f"[AI Studio] Step 3.5: Detecting face centers across {len(intervals)} caption blocks using {face_detector_model} on D drive...", flush=True)
        if progress: progress(0.35, "Tracking Faces & Choreographing Occasional Auto-Zoom...")
        intervals = detect_face_centers_for_intervals(str(video_path), intervals, face_detector_model, canvas_w, canvas_h)
        base_bg = apply_auto_zoom_to_clip(base_bg, intervals, zoom_factor, zoom_frequency, zoom_transition_style, canvas_w, canvas_h, min_cooldown_slider, zoom_hold_slider)

    video_layers = [base_bg]
    behind_speaker_text_clips = []
    in_front_speaker_text_clips = []
    outline_video_layers = []
    sfx_clips_list = []
    last_sfx_time = -999.0
    chunk_counter = 0
    sfx_base_clip = None
    if enable_sfx:
        sfx_base_clip = resolve_and_load_sfx_clip(sfx_preset_choice, sfx_upload_file, float(sfx_volume))
        if sfx_base_clip is not None:
            print(f"[AI Studio] SFX Engine ready: loaded '{sfx_preset_choice}' at volume {sfx_volume}x", flush=True)
    
    # Select font: preset or custom upload
    FONT = resolve_sans_serif_bold_font(font_preset_choice, font_file)
    print(f"[AI Studio] Resolved typography font: {FONT}", flush=True)
        
    FONT_SIZE = int(font_size)
    if "Center" in str(vertical_alignment):
        base_y_ratio = 0.50
    elif "Upper Third" in str(vertical_alignment):
        base_y_ratio = 0.28
    elif "Bottom Edge" in str(vertical_alignment):
        base_y_ratio = 0.82
    else:
        base_y_ratio = 0.60
    BASE_Y = int(canvas_h * base_y_ratio) + int(pos_offset_y)
    
    T1_TOP = hex_to_rgb(t1_top_hex)
    T1_MID = hex_to_rgb(t1_mid_hex)
    T1_BOT = hex_to_rgb(t1_bot_hex)
    T1_3D = t1_shadow_hex
    
    T2_TOP = hex_to_rgb(t2_top_hex)
    T2_MID = hex_to_rgb(t2_mid_hex)
    T2_BOT = hex_to_rgb(t2_bot_hex)
    T2_3D = t2_shadow_hex
    
    def format_caption_text(s):
        s = s.strip()
        if not s:
            return ""
        return s[0].upper() + s[1:]
    
    if progress: progress(0.4, "Compositing Graphic & Animation Layers...")
    
    for segment in segments:
        words_list = segment.get("words", [])
        if not words_list:
            continue
            
        chunk_size = max(1, int(max_words_per_chunk))
        char_limit = max(10, int(max_chars_per_line))
        is_single_line = ("single" in str(lines_per_caption).lower() or "1 line" in str(lines_per_caption).lower())

        for i in range(0, len(words_list), chunk_size):
            chunk = words_list[i:i+chunk_size]
            start_time = chunk[0]["start"]
            end_time = chunk[-1]["end"]
            chunk_duration = end_time - start_time
            if chunk_duration <= 0:
                chunk_duration = 0.1
                
            chunk_counter += 1
            if enable_sfx and sfx_base_clip is not None:
                should_trigger = False
                if "Every Single Word" in str(sfx_trigger_mode):
                    for w_item in chunk:
                        w_start = float(w_item["start"])
                        if (w_start - last_sfx_time) >= float(sfx_cooldown):
                            sfx_inst = sfx_base_clip.copy()
                            if hasattr(sfx_inst, "with_start"):
                                sfx_inst = sfx_inst.with_start(w_start)
                            else:
                                sfx_inst = sfx_inst.set_start(w_start)
                            sfx_clips_list.append(sfx_inst)
                            last_sfx_time = w_start
                elif "Every 2nd Chunk" in str(sfx_trigger_mode):
                    if chunk_counter % 2 == 1 and (start_time - last_sfx_time) >= float(sfx_cooldown):
                        should_trigger = True
                else:
                    if (start_time - last_sfx_time) >= float(sfx_cooldown):
                        should_trigger = True
                        
                if should_trigger:
                    sfx_inst = sfx_base_clip.copy()
                    if hasattr(sfx_inst, "with_start"):
                        sfx_inst = sfx_inst.with_start(start_time)
                    else:
                        sfx_inst = sfx_inst.set_start(start_time)
                    sfx_clips_list.append(sfx_inst)
                    last_sfx_time = start_time
                
            if is_single_line:
                word1_words = chunk
                word2_words = []
                word1_text = format_caption_text(" ".join(w["text"].strip() for w in word1_words))
                word2_text = ""
            else:
                if len(chunk) <= 1:
                    word1_words = chunk
                    word2_words = []
                    word1_text = format_caption_text(chunk[0]["text"]) if chunk else ""
                    word2_text = ""
                elif len(chunk) == 2:
                    word1_words = [chunk[0]]
                    word2_words = [chunk[1]]
                    word1_text = format_caption_text(chunk[0]["text"])
                    word2_text = format_caption_text(chunk[1]["text"])
                else:
                    total_words = [w["text"].strip() for w in chunk]
                    best_mid = 1
                    min_diff = float("inf")
                    for mid in range(1, len(total_words)):
                        l1 = " ".join(total_words[:mid])
                        l2 = " ".join(total_words[mid:])
                        if len(l1) > char_limit and mid > 1:
                            continue
                        diff = abs(len(l1) - len(l2))
                        if diff < min_diff:
                            min_diff = diff
                            best_mid = mid
                    word1_words = chunk[:best_mid]
                    word2_words = chunk[best_mid:]
                    word1_text = format_caption_text(" ".join(w["text"].strip() for w in word1_words))
                    word2_text = format_caption_text(" ".join(w["text"].strip() for w in word2_words))
            
            chunk_idx = i // chunk_size
            if "Chunk-Wise Alternation" in str(multi_font_mode) and chunk_idx % 2 == 1:
                curr_font_choice_1 = font_preset_choice_2 if font_preset_choice_2 != "Same as Primary Font (Single Font Mode)" else font_preset_choice
                curr_font_file_1 = font_file_2 if "Custom Uploaded" in str(font_preset_choice_2) else font_file
                curr_font_choice_2 = curr_font_choice_1
                curr_font_file_2 = curr_font_file_1
            elif "Line-Wise Contrast" in str(multi_font_mode) or "Alternating" in str(multi_font_mode):
                curr_font_choice_1 = font_preset_choice
                curr_font_file_1 = font_file
                curr_font_choice_2 = font_preset_choice_2 if font_preset_choice_2 != "Same as Primary Font (Single Font Mode)" else font_preset_choice
                curr_font_file_2 = font_file_2 if "Custom Uploaded" in str(font_preset_choice_2) else font_file
            else:
                curr_font_choice_1 = font_preset_choice
                curr_font_file_1 = font_file
                curr_font_choice_2 = font_preset_choice
                curr_font_file_2 = font_file
                
            # Check for per-word font overrides
            for w_item in word1_words:
                f_over = w_item.get("font_override", "None")
                if f_over and f_over != "None" and f_over != "None (Use Primary/Secondary)":
                    curr_font_choice_1 = f_over
                    curr_font_file_1 = None
                    break
            for w_item in word2_words:
                f_over = w_item.get("font_override", "None")
                if f_over and f_over != "None" and f_over != "None (Use Primary/Secondary)":
                    curr_font_choice_2 = f_over
                    curr_font_file_2 = None
                    break
                
            FONT_1 = resolve_sans_serif_bold_font(curr_font_choice_1, curr_font_file_1)
            FONT_2 = resolve_sans_serif_bold_font(curr_font_choice_2, curr_font_file_2)
            
            chunk_font_size = FONT_SIZE
            margin_x = 20
            margin_y = 50
            
            try:
                w1 = TextClip(text=word1_text, font=FONT_1, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0]
                w2 = TextClip(text=word2_text, font=FONT_2, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0] if word2_text else 0
            except Exception as e:
                print(f"[Warning] TextClip size check failed: {e}. Retrying with system Impact font...", flush=True)
                FONT_1 = "Impact"
                FONT_2 = "Impact"
                try:
                    w1 = TextClip(text=word1_text, font=FONT_1, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0]
                    w2 = TextClip(text=word2_text, font=FONT_2, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0] if word2_text else 0
                except Exception as e2:
                    print(f"[Error] TextClip sizing failed completely: {e2}", flush=True)
                    continue
            
            max_line_w = max(w1, w2)
            max_allowed_w = int(canvas_w * 0.9)
            
            if max_line_w > max_allowed_w:
                scale_factor = max_allowed_w / max_line_w
                chunk_font_size = max(24, int(FONT_SIZE * scale_factor))
                try:
                    w1 = TextClip(text=word1_text, font=FONT_1, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0]
                    w2 = TextClip(text=word2_text, font=FONT_2, font_size=chunk_font_size, margin=(margin_x, margin_y)).size[0] if word2_text else 0
                except Exception:
                    pass
            
            # X/Y centering is now handled exactly with true clip sizes below.
            

            # Check for per-word X/Y nudging and color overrides
            nudge_x_1 = sum(w_item.get("x_nudge", 0) for w_item in word1_words)
            nudge_y_1 = sum(w_item.get("y_nudge", 0) for w_item in word1_words)
            nudge_x_2 = sum(w_item.get("x_nudge", 0) for w_item in word2_words)
            nudge_y_2 = sum(w_item.get("y_nudge", 0) for w_item in word2_words)
            
            eff_t1_top, eff_t1_mid, eff_t1_bot = t1_top_hex, t1_mid_hex, t1_bot_hex
            for w_item in word1_words:
                c_over = w_item.get("color_override", "None")
                if c_over and c_over != "None" and c_over.startswith("#"):
                    eff_t1_top, eff_t1_mid, eff_t1_bot = c_over, c_over, c_over
                    break
                    
            eff_t2_top, eff_t2_mid, eff_t2_bot = t2_top_hex, t2_mid_hex, t2_bot_hex
            for w_item in word2_words:
                c_over = w_item.get("color_override", "None")
                if c_over and c_over != "None" and c_over.startswith("#"):
                    eff_t2_top, eff_t2_mid, eff_t2_bot = c_over, c_over, c_over
                    break
            
            has_outline_over_1 = any("Outline Over Subject" in str(w_item.get("rotoscope_override", "")) for w_item in word1_words)
            has_outline_over_2 = any("Outline Over Subject" in str(w_item.get("rotoscope_override", "")) for w_item in word2_words)
            
            wipe_dur = min(0.35, chunk_duration * 0.8)
            travel_dist = int(chunk_font_size * 1.1)
            
            # --- Generate Clips First for Exact Heights ---
            highlight_word_t1 = None
            highlight_word_t2 = None
            if random_brush_highlights and chunk_duration > 0.1:
                import hashlib
                h = int(hashlib.md5(str(round(start_time, 2)).encode()).hexdigest(), 16)
                if h % 100 < 45:
                    if word1_words: highlight_word_t1 = word1_words[h % len(word1_words)]["text"]
                    if word2_words: highlight_word_t2 = word2_words[h % len(word2_words)]["text"]

            t1_clip = render_caption_layer_image_clip(
                word1_text, font_source=curr_font_choice_1, font_upload=curr_font_file_1, font_size=chunk_font_size, is_top_layer=True, tracking=-int(chunk_font_size * 0.04),
                gloss_intensity=float(gloss_intensity), show_shadow=show_shadow, shadow_depth=int(shadow_depth),
                shadow_step_x=int(shadow_step_x), shadow_step_y=int(shadow_step_y),
                top_hex=eff_t1_top, mid_hex=eff_t1_mid, bot_hex=eff_t1_bot, shadow_hex=t1_shadow_hex,
                sheen_3d_scope=sheen_3d_scope, show_glow=show_glow, glow_hex=t1_glow_hex, glow_strength=glow_strength,
                highlight_word=highlight_word_t1
            )
            t1_w, t1_h = t1_clip.size
            pos_x_t1 = (canvas_w - t1_w) // 2 + int(pos_offset_x) + nudge_x_1
            
            t2_w, t2_h = 0, 0
            if word2_text:
                t2_clip = render_caption_layer_image_clip(
                    word2_text, font_source=curr_font_choice_2, font_upload=curr_font_file_2, font_size=chunk_font_size, is_top_layer=False, tracking=-int(chunk_font_size * 0.04),
                    gloss_intensity=float(gloss_intensity), show_shadow=show_shadow, shadow_depth=int(shadow_depth),
                    shadow_step_x=int(shadow_step_x), shadow_step_y=int(shadow_step_y),
                    top_hex=eff_t2_top, mid_hex=eff_t2_mid, bot_hex=eff_t2_bot, shadow_hex=t2_shadow_hex,
                    sheen_3d_scope=sheen_3d_scope, show_glow=show_glow, glow_hex=t2_glow_hex, glow_strength=glow_strength,
                    highlight_word=highlight_word_t2
                )
                t2_w, t2_h = t2_clip.size
                pos_x_t2 = (canvas_w - t2_w) // 2 + int(pos_offset_x) + nudge_x_2

            # --- Apply Perfect Vertical Centering Math (Matches Live Preview) ---
            Y1 = 30 + nudge_y_1
            if word2_text:
                line_gap = int(chunk_font_size * 0.82 * float(line_spacing_scale))
                Y2 = 30 + line_gap + nudge_y_2
                B_top = min(Y1, Y2)
                B_bot = max(Y1 + t1_h, Y2 + t2_h)
            else:
                B_top = Y1
                B_bot = Y1 + t1_h
            
            H_stack = B_bot - B_top
            Y_start = BASE_Y - H_stack // 2
            
            base_y_t1 = Y_start + (Y1 - B_top)
            if word2_text:
                base_y_t2 = Y_start + (Y2 - B_top)
            
            if bg_box_enable:
                from PIL import Image, ImageDraw


                h_est = int(chunk_font_size * 1.4)
                min_x = pos_x_t1
                max_x = min_x + w1
                min_y = base_y_t1
                max_y = min_y + h_est
                if word2_text:
                    x2 = pos_x_t2
                    min_x = min(min_x, x2)
                    max_x = max(max_x, x2 + w2)
                    y2 = base_y_t2
                    min_y = min(min_y, y2)
                    max_y = max(max_y, y2 + h_est)
                
                pad_x, pad_y = 15, 10
                box_w = int((max_x - min_x) + pad_x * 2)
                box_h = int((max_y - min_y) + pad_y * 2)
                
                bg_img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
                draw_bg = ImageDraw.Draw(bg_img)
                rect_color = bg_box_color
                if rect_color.startswith('#') and len(rect_color) == 7:
                    rect_color = rect_color + "FF"
                draw_bg.rounded_rectangle([0, 0, box_w, box_h], radius=15, fill=rect_color)
                
                bg_clip = ImageClip(np.array(bg_img)).with_start(start_time).with_end(end_time)
                bg_pos_x = int(min_x - pad_x)
                bg_pos_y = int(min_y - pad_y)
                bg_clip = bg_clip.with_position((bg_pos_x, bg_pos_y))
                
                is_t1_in_front = any("In Front of Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word1_words)
                is_t1_behind = any("Text Behind Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word1_words)
                if not is_t1_in_front and (is_t1_behind or (rotoscope_enable and "Text Behind Speaker" in str(rotoscope_style)) or (rotoscope_enable and ("Outline Over Subject" in str(rotoscope_style) or has_outline_over_1))):
                    behind_speaker_text_clips.append(bg_clip)
                else:
                    in_front_speaker_text_clips.append(bg_clip)
            
            # --- LINE 1 (Top Line: PIL Extruded Plastic 3D & Specular Sheen + Soft Wipe) ---
            
            t1_animated = apply_wipe_filter(t1_clip, duration=wipe_dur, feather_width=35).with_start(start_time).with_end(end_time).with_position((pos_x_t1, base_y_t1))
            
            is_t1_in_front = any("In Front of Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word1_words)
            is_t1_behind = any("Text Behind Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word1_words)
            if not is_t1_in_front and (is_t1_behind or (rotoscope_enable and "Text Behind Speaker" in str(rotoscope_style)) or (rotoscope_enable and ("Outline Over Subject" in str(rotoscope_style) or has_outline_over_1))):
                behind_speaker_text_clips.append(t1_animated)
            else:
                in_front_speaker_text_clips.append(t1_animated)
            
            if rotoscope_enable and ("Outline Over Subject" in str(rotoscope_style) or has_outline_over_1):
                t1_out_clip = render_caption_layer_image_clip(
                    word1_text, font_source=curr_font_choice_1, font_upload=curr_font_file_1, font_size=chunk_font_size, is_top_layer=True, tracking=-int(chunk_font_size * 0.04),
                    gloss_intensity=float(gloss_intensity), show_shadow=False, shadow_depth=int(shadow_depth),
                    shadow_step_x=int(shadow_step_x), shadow_step_y=int(shadow_step_y),
                    top_hex=eff_t1_top, mid_hex=eff_t1_mid, bot_hex=eff_t1_bot, shadow_hex=t1_shadow_hex,
                    sheen_3d_scope=sheen_3d_scope, outline_only=True, stroke_width=int(rotoscope_outline_width),
                    show_glow=show_glow, glow_hex=t1_glow_hex, glow_strength=glow_strength,
                    highlight_word=highlight_word_t1
                )
                t1_out_anim = apply_wipe_filter(t1_out_clip, duration=wipe_dur, feather_width=35).with_start(start_time).with_end(end_time).with_position((pos_x_t1, base_y_t1))
                outline_video_layers.append(t1_out_anim)
            
            # --- LINE 2 (Bottom Line: Crisp White / Custom Sheen + Pop-in Rise + Kinetic Zoom Bounce + Rotational Tilt) ---
            if word2_text:
                
                rise_anim_core = make_rise_anim(pos_x_t2, base_y_t2, chunk_duration, travel_dist, offset_x=0, offset_y=0)
                t2_animated = t2_clip.resized(lambda t: get_spring_scale(t)).rotated(lambda t: get_entry_tilt(t), expand=True)
                t2_animated = t2_animated.with_start(start_time).with_end(end_time).with_position(rise_anim_core)
                
                is_t2_in_front = any("In Front of Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word2_words)
                is_t2_behind = any("Text Behind Speaker" in str(w_item.get("rotoscope_override", "")) for w_item in word2_words)
                has_outline_over_2 = any("Outline Over Subject" in str(w_item.get("rotoscope_override", "")) for w_item in word2_words)
                
                if is_t2_behind or has_outline_over_2:
                    behind_speaker_text_clips.append(t2_animated)
                else:
                    in_front_speaker_text_clips.append(t2_animated)
                
                if has_outline_over_2:
                    t2_out_clip = render_caption_layer_image_clip(
                        word2_text, font_source=curr_font_choice_2, font_upload=curr_font_file_2, font_size=chunk_font_size, is_top_layer=False, tracking=-int(chunk_font_size * 0.04),
                        gloss_intensity=float(gloss_intensity), show_shadow=False, shadow_depth=int(shadow_depth),
                        shadow_step_x=int(shadow_step_x), shadow_step_y=int(shadow_step_y),
                        top_hex=eff_t2_top, mid_hex=eff_t2_mid, bot_hex=eff_t2_bot, shadow_hex=t2_shadow_hex,
                        sheen_3d_scope=sheen_3d_scope, outline_only=True, stroke_width=int(rotoscope_outline_width),
                        show_glow=show_glow, glow_hex=t2_glow_hex, glow_strength=glow_strength
                    )
                    t2_out_anim = t2_out_clip.resized(lambda t: get_spring_scale(t)).rotated(lambda t: get_entry_tilt(t), expand=True)
                    t2_out_anim = t2_out_anim.with_start(start_time).with_end(end_time).with_position(rise_anim_core)
                    outline_video_layers.append(t2_out_anim)

    if rotoscope_enable and custom_roto_text and str(custom_roto_text).strip():
        print(f"[AI Studio] Generating Custom Rotoscope Text '{custom_roto_text}' from {rotoscope_start_sec}s to {rotoscope_end_sec}s...", flush=True)
        custom_roto_clip = render_caption_layer_image_clip(
            custom_roto_text, font_source=custom_roto_font, font_upload=None, font_size=int(custom_roto_font_size), is_top_layer=True, tracking=-int(custom_roto_font_size * 0.04),
            gloss_intensity=0.0, show_shadow=False, shadow_depth=0,
            shadow_step_x=0, shadow_step_y=0,
            top_hex=custom_roto_color, mid_hex=custom_roto_color, bot_hex=custom_roto_color, shadow_hex="#000000",
            sheen_3d_scope=100.0, show_glow=custom_roto_show_glow, glow_hex=custom_roto_glow_color, glow_strength=float(custom_roto_glow_strength)
        )
        custom_w, custom_h = custom_roto_clip.size
        c_pos_x = (canvas_w - custom_w) // 2 + int(custom_roto_pos_x)
        c_pos_y = (canvas_h - custom_h) // 2 + int(custom_roto_pos_y)
        custom_animated = custom_roto_clip.with_start(float(rotoscope_start_sec)).with_end(float(rotoscope_end_sec)).with_position((c_pos_x, c_pos_y))
        behind_speaker_text_clips.append(custom_animated)

    if progress: progress(0.8, "Compositing Canvas & Exporting Video...")
    final_audio = audio_clip
    if enable_sfx and sfx_base_clip is not None and len(sfx_clips_list) > 0:
        print(f"[AI Studio] Compositing {len(sfx_clips_list)} SFX pop-up audio events into master soundtrack...", flush=True)
        try:
            from moviepy import CompositeAudioClip
            if audio_clip is not None:
                final_audio = CompositeAudioClip([audio_clip] + sfx_clips_list)
            else:
                final_audio = CompositeAudioClip(sfx_clips_list)
        except Exception as e_audio:
            print(f"[Warning] Failed to composite SFX audio ({e_audio}). Using base audio.", flush=True)
            final_audio = audio_clip

    if rotoscope_enable and media_clip is not None and float(rotoscope_end_sec) > float(rotoscope_start_sec) and (len(behind_speaker_text_clips) > 0 or "Outline Over Subject" in str(rotoscope_style) or len(outline_video_layers) > 0):
        print(f"[AI Studio] Step 3.8: Applying AI Rotoscope (Layer 2: Behind Speaker | Layer 4: In Front) from t={rotoscope_start_sec}s to t={rotoscope_end_sec}s...", flush=True)
        ds_ratio = 0.25
        if "0.50" in str(rotoscope_downsample):
            ds_ratio = 0.50
        elif "0.125" in str(rotoscope_downsample):
            ds_ratio = 0.125
            
        rvm_state = {"rec": [None] * 4, "last_t": -1.0}
        
        outline_video = None
        if len(outline_video_layers) > 0:
            print(f"[AI Studio] Building synchronized Outline Video Clip ({len(outline_video_layers)} layers) for Media Inside Text Masking...", flush=True)
            try:
                outline_video = CompositeVideoClip(outline_video_layers, size=(canvas_w, canvas_h))
            except Exception as e_out_comp:
                print(f"[Warning] Failed to composite outline video: {e_out_comp}", flush=True)
        
        def rotoscope_frame_filter(get_frame, t):
            caption_frame = get_frame(t)
            is_any_behind_clip_active = any(hasattr(clip, "start") and hasattr(clip, "end") and clip.start <= t <= clip.end for clip in behind_speaker_text_clips)
            is_any_outline_clip_active = any(hasattr(clip, "start") and hasattr(clip, "end") and clip.start <= t <= clip.end for clip in outline_video_layers)
            if float(rotoscope_start_sec) <= t <= float(rotoscope_end_sec) and (is_any_behind_clip_active or is_any_outline_clip_active):
                if t < rvm_state["last_t"] or (t - rvm_state["last_t"]) > 0.5:
                    rvm_state["rec"] = [None] * 4
                rvm_state["last_t"] = t
                try:
                    src_frame = media_clip.get_frame(t)
                    fgr, pha, new_rec = get_rvm_mask(src_frame, rvm_state["rec"], downsample_ratio=ds_ratio)
                    if fgr is not None and pha is not None:
                        rvm_state["rec"] = new_rec
                        out = caption_frame * (1.0 - pha) + fgr * pha
                        if outline_video is not None and hasattr(outline_video, "mask") and outline_video.mask is not None:
                            try:
                                outline_rgb = outline_video.get_frame(t)
                                outline_alpha = outline_video.mask.get_frame(t)
                                if outline_alpha.ndim == 2:
                                    outline_alpha = outline_alpha[:, :, np.newaxis]
                                out = out * (1.0 - outline_alpha) + outline_rgb * outline_alpha
                            except Exception as e_out:
                                pass
                        return out.astype(np.uint8)
                except Exception as e_roto:
                    print(f"[Warning] Rotoscope frame error at t={t:.2f}s: {e_roto}", flush=True)
                    with open(os.path.join(config.OUTPUT_DIR, "rotoscope_debug.txt"), "a") as f:
                        f.write(f"Error at {t}: {e_roto}\n")
                        try:
                            f.write(f"caption_frame shape: {caption_frame.shape}\n")
                            f.write(f"src_frame shape: {src_frame.shape}\n")
                            f.write(f"pha shape: {pha.shape if 'pha' in locals() and pha is not None else 'None'}\n")
                        except Exception:
                            pass
            return caption_frame
            
        base_behind_comp = CompositeVideoClip([base_bg] + behind_speaker_text_clips, size=(canvas_w, canvas_h))
        if hasattr(base_behind_comp, "transform"):
            rotoscoped_base_video = base_behind_comp.transform(rotoscope_frame_filter)
        elif hasattr(base_behind_comp, "fl"):
            rotoscoped_base_video = base_behind_comp.fl(rotoscope_frame_filter)
        else:
            rotoscoped_base_video = base_behind_comp
            
        final_video = CompositeVideoClip([rotoscoped_base_video] + in_front_speaker_text_clips, size=(canvas_w, canvas_h)).with_audio(final_audio)
    else:
        final_video = CompositeVideoClip([base_bg] + behind_speaker_text_clips + in_front_speaker_text_clips, size=(canvas_w, canvas_h)).with_audio(final_audio)

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    if has_video:
        base_name = os.path.splitext(os.path.basename(video_path))[0]
    else:
        base_name = os.path.splitext(os.path.basename(audio_path))[0]

    if "Burn directly" in str(output_mode):
        output_path = os.path.join(output_dir, f"{base_name}_burn_in.mp4")
        print(f"[AI Studio] Step 4: Exporting Burn-In video to '{output_path}'...", flush=True)
        final_video.write_videofile(
            output_path, 
            fps=30, 
            codec="libx264", 
            audio_codec="aac", 
            temp_audiofile=os.path.join(output_dir, f"{base_name}_TEMP_audio_burn.mp4"),
            logger="bar"
        )
    else:
        output_path = os.path.join(output_dir, f"{base_name}_green_screen.mp4")
        print(f"[AI Studio] Step 4: Exporting Green Screen video to '{output_path}'...", flush=True)
        final_video.write_videofile(
            output_path, 
            fps=30, 
            codec="libx264", 
            audio_codec="aac", 
            temp_audiofile=os.path.join(output_dir, f"{base_name}_TEMP_audio_green.mp4"),
            logger="bar"
        )
    final_video.close()
    if base_bg is not None and base_bg is not media_clip:
        base_bg.close()
    if media_clip is not None:
        media_clip.close()
    if audio_clip is not None and hasattr(audio_clip, 'close'):
        try:
            audio_clip.close()
        except Exception:
            pass
    if sfx_base_clip is not None and hasattr(sfx_base_clip, 'close'):
        try:
            sfx_base_clip.close()
        except Exception:
            pass
    
    print(f"\n[AI Studio] SUCCESS! Rendered video output written to '{output_path}'!", flush=True)
    if progress: progress(1.0, "Done!")
    return output_path


# ==========================================
# 3.5. PRESET MANAGEMENT ENGINE (SAVE / LOAD)
# ==========================================

def save_studio_preset_gui(
    preset_name, font_preset, multi_font_mode, font_preset_2, font_size, show_shadow, shadow_depth, shadow_step_x, shadow_step_y,
    sheen_3d_scope, gloss_intensity, t1_top, t1_mid, t1_bot, t1_shadow, t2_top, t2_mid, t2_bot, t2_shadow,
    show_glow, t1_glow, t2_glow,
    max_words, max_chars, lines_mode, line_spacing, vertical_align, offset_x, offset_y, output_mode,
    enable_zoom, zoom_fac, zoom_freq, zoom_trans, face_model, min_cooldown, zoom_hold,
    enable_sfx, sfx_preset, sfx_volume, sfx_trigger, sfx_cooldown,
    rotoscope_enable, rotoscope_style, rotoscope_outline_width, rotoscope_start_sec, rotoscope_end_sec, rotoscope_downsample
):
    try:
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in str(preset_name).strip())
        if not safe_name:
            safe_name = "studio_preset"
        filename = os.path.join(config.OUTPUT_DIR, f"{safe_name}.json")
        
        preset_data = {
            "preset_name": str(preset_name),
            "version": "2.9.0",
            "settings": {
                "font_preset": str(font_preset),
                "multi_font_mode": str(multi_font_mode),
                "font_preset_2": str(font_preset_2),
                "font_size": float(font_size),
                "show_shadow": bool(show_shadow),
                "shadow_depth": int(shadow_depth),
                "shadow_step_x": int(shadow_step_x),
                "shadow_step_y": int(shadow_step_y),
                "sheen_3d_scope": str(sheen_3d_scope),
                "gloss_intensity": float(gloss_intensity),
                "t1_top": str(t1_top),
                "t1_mid": str(t1_mid),
                "t1_bot": str(t1_bot),
                "t1_shadow": str(t1_shadow),
                "t2_top": str(t2_top),
                "t2_mid": str(t2_mid),
                "t2_bot": str(t2_bot),
                "t2_shadow": str(t2_shadow),
                "show_glow": bool(show_glow),
                "t1_glow": str(t1_glow),
                "t2_glow": str(t2_glow),
                "max_words_per_chunk": int(max_words),
                "max_chars_per_line": int(max_chars),
                "lines_mode": str(lines_mode),
                "line_spacing_scale": float(line_spacing),
                "vertical_alignment": str(vertical_align),
                "pos_offset_x": int(offset_x),
                "pos_offset_y": int(offset_y),
                "output_mode": str(output_mode),
                "enable_auto_zoom": bool(enable_zoom),
                "zoom_factor": float(zoom_fac),
                "zoom_frequency": str(zoom_freq),
                "zoom_transition_style": str(zoom_trans),
                "face_detector_model": str(face_model),
                "min_cooldown": float(min_cooldown),
                "zoom_hold": float(zoom_hold),
                "enable_sfx": bool(enable_sfx),
                "sfx_preset": str(sfx_preset),
                "sfx_volume": float(sfx_volume),
                "sfx_trigger_mode": str(sfx_trigger),
                "sfx_cooldown": float(sfx_cooldown),
                "rotoscope_enable": bool(rotoscope_enable),
                "rotoscope_style": str(rotoscope_style),
                "rotoscope_outline_width": int(rotoscope_outline_width),
                "rotoscope_start_sec": float(rotoscope_start_sec),
                "rotoscope_end_sec": float(rotoscope_end_sec),
                "rotoscope_downsample": str(rotoscope_downsample)
            }
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=4)
            
        status_html = f"<div style='color: #4ADE80; font-weight: 600; padding: 12px; background: #064E3B; border-radius: 6px;'>✅ Studio Preset '{preset_name}' exported successfully to '{filename}'! Click below to download.</div>"
        return filename, status_html
    except Exception as e:
        status_html = f"<div style='color: #F87171; font-weight: 600; padding: 12px; background: #450A0A; border-radius: 6px;'>❌ Error exporting preset: {str(e)}</div>"
        return None, status_html

def load_studio_preset_gui(
    filepath, font_preset, multi_font_mode, font_preset_2, font_size, show_shadow, shadow_depth, shadow_step_x, shadow_step_y,
    sheen_3d_scope, gloss_intensity, t1_top, t1_mid, t1_bot, t1_shadow, t2_top, t2_mid, t2_bot, t2_shadow,
    show_glow, t1_glow, t2_glow,
    max_words, max_chars, lines_mode, line_spacing, vertical_align, offset_x, offset_y, output_mode,
    enable_zoom, zoom_fac, zoom_freq, zoom_trans, face_model, min_cooldown, zoom_hold,
    enable_sfx, sfx_preset, sfx_volume, sfx_trigger, sfx_cooldown,
    rotoscope_enable, rotoscope_style, rotoscope_outline_width, rotoscope_start_sec, rotoscope_end_sec, rotoscope_downsample
):
    if not filepath or not os.path.exists(str(filepath)):
        status_html = "<div style='color: #F87171; font-weight: 600; padding: 12px; background: #450A0A; border-radius: 6px;'>❌ Please select or upload a valid .json preset file first!</div>"
        return [font_preset, multi_font_mode, font_preset_2, font_size, show_shadow, shadow_depth, shadow_step_x, shadow_step_y,
                sheen_3d_scope, gloss_intensity, t1_top, t1_mid, t1_bot, t1_shadow, t2_top, t2_mid, t2_bot, t2_shadow,
                show_glow, t1_glow, t2_glow,
                max_words, max_chars, lines_mode, line_spacing, vertical_align, offset_x, offset_y, output_mode,
                enable_zoom, zoom_fac, zoom_freq, zoom_trans, face_model, min_cooldown, zoom_hold,
                enable_sfx, sfx_preset, sfx_volume, sfx_trigger, sfx_cooldown,
                rotoscope_enable, rotoscope_style, rotoscope_outline_width, rotoscope_start_sec, rotoscope_end_sec, rotoscope_downsample, status_html]
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        s = data.get("settings", data)
        preset_name = data.get("preset_name", os.path.basename(str(filepath)))
        
        status_html = f"<div style='color: #4ADE80; font-weight: 600; padding: 12px; background: #064E3B; border-radius: 6px;'>🎉 Successfully loaded and applied preset: '{preset_name}'!</div>"
        
        return [
            str(s.get("font_preset", font_preset)),
            str(s.get("multi_font_mode", multi_font_mode)),
            str(s.get("font_preset_2", font_preset_2)),
            float(s.get("font_size", font_size)),
            bool(s.get("show_shadow", show_shadow)),
            int(s.get("shadow_depth", shadow_depth)),
            int(s.get("shadow_step_x", shadow_step_x)),
            int(s.get("shadow_step_y", shadow_step_y)),
            str(s.get("sheen_3d_scope", sheen_3d_scope)),
            float(s.get("gloss_intensity", gloss_intensity)),
            str(s.get("t1_top", t1_top)),
            str(s.get("t1_mid", t1_mid)),
            str(s.get("t1_bot", t1_bot)),
            str(s.get("t1_shadow", t1_shadow)),
            str(s.get("t2_top", t2_top)),
            str(s.get("t2_mid", t2_mid)),
            str(s.get("t2_bot", t2_bot)),
            str(s.get("t2_shadow", t2_shadow)),
            bool(s.get("show_glow", show_glow)),
            str(s.get("t1_glow", t1_glow)),
            str(s.get("t2_glow", t2_glow)),
            int(s.get("max_words_per_chunk", max_words)),
            int(s.get("max_chars_per_line", max_chars)),
            str(s.get("lines_mode", lines_mode)),
            float(s.get("line_spacing_scale", line_spacing)),
            str(s.get("vertical_alignment", vertical_align)),
            int(s.get("pos_offset_x", offset_x)),
            int(s.get("pos_offset_y", offset_y)),
            str(s.get("output_mode", output_mode)),
            bool(s.get("enable_auto_zoom", enable_zoom)),
            float(s.get("zoom_factor", zoom_fac)),
            str(s.get("zoom_frequency", zoom_freq)),
            str(s.get("zoom_transition_style", zoom_trans)),
            str(s.get("face_detector_model", face_model)),
            float(s.get("min_cooldown", min_cooldown)),
            float(s.get("zoom_hold", zoom_hold)),
            bool(s.get("enable_sfx", enable_sfx)),
            str(s.get("sfx_preset", sfx_preset)),
            float(s.get("sfx_volume", sfx_volume)),
            str(s.get("sfx_trigger_mode", sfx_trigger)),
            float(s.get("sfx_cooldown", sfx_cooldown)),
            bool(s.get("rotoscope_enable", rotoscope_enable)),
            str(s.get("rotoscope_style", rotoscope_style)),
            int(s.get("rotoscope_outline_width", rotoscope_outline_width)),
            float(s.get("rotoscope_start_sec", rotoscope_start_sec)),
            float(s.get("rotoscope_end_sec", rotoscope_end_sec)),
            str(s.get("rotoscope_downsample", rotoscope_downsample)),
            status_html
        ]
    except Exception as e:
        status_html = f"<div style='color: #F87171; font-weight: 600; padding: 12px; background: #450A0A; border-radius: 6px;'>❌ Error loading preset file: {str(e)}</div>"
        return [font_preset, multi_font_mode, font_preset_2, font_size, show_shadow, shadow_depth, shadow_step_x, shadow_step_y,
                sheen_3d_scope, gloss_intensity, t1_top, t1_mid, t1_bot, t1_shadow, t2_top, t2_mid, t2_bot, t2_shadow,
                show_glow, t1_glow, t2_glow,
                max_words, max_chars, lines_mode, line_spacing, vertical_align, offset_x, offset_y, output_mode,
                enable_zoom, zoom_fac, zoom_freq, zoom_trans, face_model, min_cooldown, zoom_hold,
                enable_sfx, sfx_preset, sfx_volume, sfx_trigger, sfx_cooldown,
                rotoscope_enable, rotoscope_style, rotoscope_outline_width, rotoscope_start_sec, rotoscope_end_sec, rotoscope_downsample, status_html]


# ==========================================
# 4. CUSTOM NEUMORPHIC INTERFACE LAYOUT & CSS
# ==========================================

