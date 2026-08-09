import numpy as np
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
from moviepy import TextClip, ImageClip

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
            
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
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
                return ImageFont.truetype(c, int(font_size))
            except Exception:
                pass
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
    outline_only=False, stroke_width=3, show_glow=True, glow_hex="#FF7300"
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
            ao_factor = max(0.25, 1.0 - (math.pow(i / max(1, depth), 1.2)) * 0.65)
            r_ao = int(shadow_rgb[0] * ao_factor)
            g_ao = int(shadow_rgb[1] * ao_factor)
            b_ao = int(shadow_rgb[2] * ao_factor)
            layer_i = Image.new("RGBA", (w, h), (r_ao, g_ao, b_ao, 255))
            layer_i.putalpha(text_mask)
            composite.alpha_composite(layer_i, (i * s_x, i * s_y))
            
    # Outer Ambient Glow / Halo
    if show_glow and glow_hex and str(glow_hex).strip().lower() != "none":
        glow_rgb = hex_to_rgb(glow_hex)
        glow_mask = text_mask.filter(ImageFilter.GaussianBlur(radius=max(6, int(font.size * 0.085))))
        glow_layer = Image.new("RGBA", (w, h), (glow_rgb[0], glow_rgb[1], glow_rgb[2], 210))
        glow_layer.putalpha(glow_mask)
        composite.alpha_composite(glow_layer, (0, 0))
    
    composite.alpha_composite(base_grad, (0, 0))
    composite.alpha_composite(shine_layer, (0, 0))
    return composite

def build_bottom_layer_stark_white(
    text, font, tracking=-4, pad=40,
    top_hex="#FFFFFF", mid_hex="#CCCCCC", bot_hex="#AAAAAA", shadow_hex="#0A0A0A",
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    outline_only=False, stroke_width=3, show_glow=False, glow_hex="#FFFFFF"
):
    """
    Layer 2: Bottom Text Appearance ("Disconnected videos")
    - Stark, high-contrast pure white or sleek custom sheen
    - Heavy opaque black drop shadow with Gaussian blur, offset downwards and slightly right
    """
    text_mask = create_tight_text_mask(text, font, tracking=tracking, pad=pad, outline_only=outline_only, stroke_width=stroke_width)
    w, h = text_mask.size
    
    if outline_only:
        if top_hex.upper() == "#FFFFFF" and bot_hex.upper() in ("#FFFFFF", "#AAAAAA"):
            core_layer = Image.new("RGBA", (w, h), (255, 255, 255, 255))
            core_layer.putalpha(text_mask)
            return core_layer
        else:
            return build_top_layer_extruded_plastic(
                text, font, tracking=tracking, pad=pad,
                top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
                gloss_intensity=gloss_intensity, show_shadow=False,
                outline_only=True, stroke_width=stroke_width,
                show_glow=show_glow, glow_hex=glow_hex
            )
            
    # If custom color is picked or pure white
    if top_hex.upper() == "#FFFFFF" and bot_hex.upper() in ("#FFFFFF", "#AAAAAA"):
        core_layer = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        core_layer.putalpha(text_mask)
    else:
        # Render custom gradient with gloss sheen
        core_layer = build_top_layer_extruded_plastic(
            text, font, tracking=tracking, pad=pad,
            top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
            gloss_intensity=gloss_intensity, show_shadow=False,
            show_glow=show_glow, glow_hex=glow_hex
        )
        
    offset_x = max(3, int(font.size * 0.03))
    offset_y = max(5, int(font.size * 0.055))
    shadow_mask = ImageChops.offset(text_mask, offset_x, offset_y)
    draw_s = ImageDraw.Draw(shadow_mask)
    draw_s.rectangle([0, 0, w, offset_y], fill=0)
    draw_s.rectangle([0, 0, offset_x, h], fill=0)
    shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=max(4, int(font.size * 0.055))))
    
    shadow_layer = Image.new("RGBA", (w, h), (10, 12, 18, 240))
    shadow_layer.putalpha(shadow_mask)
    
    composite = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if show_glow and glow_hex and str(glow_hex).strip().lower() != "none":
        glow_rgb = hex_to_rgb(glow_hex)
        glow_mask = text_mask.filter(ImageFilter.GaussianBlur(radius=max(6, int(font.size * 0.085))))
        glow_layer = Image.new("RGBA", (w, h), (glow_rgb[0], glow_rgb[1], glow_rgb[2], 210))
        glow_layer.putalpha(glow_mask)
        composite = Image.alpha_composite(composite, glow_layer)
    if show_shadow:
        composite = Image.alpha_composite(composite, shadow_layer)
    composite = Image.alpha_composite(composite, core_layer)
    return composite

def render_stacked_captions_png(
    text_top, text_bottom, font_source=None, font_upload=None, font_source_2=None, font_upload_2=None, font_size=135, bottom_font_size=135, tracking=-5, leading=6,
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    t1_top_hex="#FFD56B", t1_mid_hex="#FF7300", t1_bot_hex="#E53900", t1_shadow_hex="#1A0000",
    t2_top_hex="#FFFFFF", t2_mid_hex="#CCCCCC", t2_bot_hex="#AAAAAA", t2_shadow_hex="#0A0A0A",
    line_spacing_scale=0.82, sheen_3d_scope="Both Lines (Top + Bottom - Default)",
    outline_only=False, stroke_width=3, show_glow=True, t1_glow_hex="#FF7300", t2_glow_hex="None"
):
    """Creates a cohesive, stacked block of text with minimal line height and full 3D metallic gloss."""
    font_1 = resolve_pil_font(font_source, font_size, custom_upload_file=font_upload)
    if font_source_2 and font_source_2 != "Same as Primary Font (Single Font Mode)":
        font_2 = resolve_pil_font(font_source_2, bottom_font_size, custom_upload_file=font_upload_2)
        if font_2 is None:
            font_2 = resolve_pil_font(font_source_2, bottom_font_size, custom_upload_file=font_upload_2)
    else:
        font_2 = resolve_pil_font(font_source_2, bottom_font_size, custom_upload_file=font_upload_2)
        
    l1_shadow = show_shadow if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else False
    l1_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else 0.0
    
    l2_shadow = show_shadow if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else False
    l2_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else 0.0
        
    img_top = build_top_layer_extruded_plastic(
        text_top, font_1, tracking=tracking, pad=35,
        top_hex=t1_top_hex, mid_hex=t1_mid_hex, bot_hex=t1_bot_hex, shadow_hex=t1_shadow_hex,
        gloss_intensity=l1_gloss, show_shadow=l1_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        outline_only=outline_only, stroke_width=stroke_width,
        show_glow=show_glow, glow_hex=t1_glow_hex
    )
    img_bot = build_bottom_layer_stark_white(
        text_bottom, font_2, tracking=tracking, pad=35,
        top_hex=t2_top_hex, mid_hex=t2_mid_hex, bot_hex=t2_bot_hex, shadow_hex=t2_shadow_hex,
        gloss_intensity=l2_gloss, show_shadow=l2_shadow, shadow_depth=shadow_depth,
        shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
        outline_only=outline_only, stroke_width=stroke_width,
        show_glow=show_glow, glow_hex=t2_glow_hex
    )
    
    bbox_top = img_top.getbbox()
    bbox_bot = img_bot.getbbox()
    w_top, h_top = img_top.size
    w_bot, h_bot = img_bot.size
    
    final_w = max(w_top, w_bot) + 40
    
    x_top = (final_w - w_top) // 2
    y_top = 30
    x_bot = (final_w - w_bot) // 2
    
    if text_bottom:
        line_gap = int(font_size * 0.82 * float(line_spacing_scale))
        y_bot = y_top + line_gap
    else:
        y_bot = y_top + h_top
        
    final_h = max(y_top + h_top, y_bot + h_bot) + 30
    stacked = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    stacked.alpha_composite(img_top, (x_top, y_top))
    if text_bottom:
        stacked.alpha_composite(img_bot, (x_bot, y_bot))
        
    return stacked

def render_caption_layer_image_clip(
    text, font_source=None, font_upload=None, font_size=135, is_top_layer=True, tracking=-4,
    gloss_intensity=0.7, show_shadow=True, shadow_depth=3, shadow_step_x=1, shadow_step_y=1,
    top_hex="#FFD56B", mid_hex="#FF7300", bot_hex="#E53900", shadow_hex="#1A0000",
    sheen_3d_scope="Both Lines (Top + Bottom - Default)",
    outline_only=False, stroke_width=3, show_glow=True, glow_hex="#FF7300"
):
    """Converts a PIL rendered transparent caption layer into a MoviePy ImageClip with proper RGBA mask."""
    font = resolve_pil_font(font_source, font_size, custom_upload_file=font_upload)
    if is_top_layer:
        eff_shadow = show_shadow if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else False
        eff_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Top Line Only" in str(sheen_3d_scope)) else 0.0
        pil_img = build_top_layer_extruded_plastic(
            text, font, tracking=tracking, pad=35,
            top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
            gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
            shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
            outline_only=outline_only, stroke_width=stroke_width,
            show_glow=show_glow, glow_hex=glow_hex
        )
    else:
        eff_shadow = show_shadow if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else False
        eff_gloss = float(gloss_intensity) if ("Both Lines" in str(sheen_3d_scope) or "Bottom Line Only" in str(sheen_3d_scope)) else 0.0
        pil_img = build_bottom_layer_stark_white(
            text, font, tracking=tracking, pad=35,
            top_hex=top_hex, mid_hex=mid_hex, bot_hex=bot_hex, shadow_hex=shadow_hex,
            gloss_intensity=eff_gloss, show_shadow=eff_shadow, shadow_depth=shadow_depth,
            shadow_step_x=shadow_step_x, shadow_step_y=shadow_step_y,
            outline_only=outline_only, stroke_width=stroke_width,
            show_glow=show_glow, glow_hex=glow_hex
        )
    arr = np.array(pil_img)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0
    try:
        mask_clip = ImageClip(alpha, is_mask=True)
    except TypeError:
        mask_clip = ImageClip(alpha, ismask=True)
    return ImageClip(rgb).with_mask(mask_clip)

