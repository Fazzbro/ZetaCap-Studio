import os
import numpy as np
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy import ImageClip, CompositeVideoClip, VideoFileClip

def generate_starry_background(width, height, num_stars=200):
    """Generates a static starry night background ImageClip."""
    img = Image.new("RGBA", (width, height), (5, 5, 10, 255))
    draw = ImageDraw.Draw(img)
    
    for _ in range(num_stars):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        size = random.choice([1, 1, 1, 2, 3]) 
        alpha = random.randint(100, 255)
        draw.ellipse([x, y, x + size, y + size], fill=(255, 255, 255, alpha))
        
    # Extract RGB only for the background to be fully opaque
    rgb = np.array(img)[:, :, :3]
    return ImageClip(rgb)

def render_highlighted_text(text, highlighted_word, font_path, font_size=120):
    """
    Renders text horizontally centered. 
    The highlighted_word is colored neon green with a glowing underline.
    Returns a MoviePy ImageClip with an alpha mask.
    """
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        font = ImageFont.load_default()
        
    words = text.split()
    
    total_width = 0
    max_height = 0
    word_metrics = []
    
    for w in words:
        bbox = font.getbbox(w)
        # width of the word
        adv = font.getlength(w)
        total_width += adv
        max_height = max(max_height, bbox[3] - bbox[1])
        word_metrics.append({"word": w, "width": adv, "bbox": bbox})
        
    space_width = font.getlength(" ")
    total_width += space_width * (len(words) - 1)
    
    canvas_w = int(total_width) + 200
    canvas_h = int(max_height) + 200
    
    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    current_x = 100
    # Position text so there is room for the underline
    base_y = int((canvas_h - max_height) / 2)
    
    neon_green = "#39FF14"
    
    for metrics in word_metrics:
        w = metrics["word"]
        clean_w = ''.join(e for e in w if e.isalnum()).lower()
        clean_target = ''.join(e for e in highlighted_word if e.isalnum()).lower()
        
        if clean_w == clean_target:
            draw.text((current_x, base_y), w, font=font, fill=neon_green)
            
            line_y = base_y + metrics["bbox"][3] + 15
            line_x_start = current_x
            line_x_end = current_x + metrics["width"]
            
            draw.line((line_x_start, line_y, line_x_end, line_y), fill=neon_green, width=int(font_size*0.08))
        else:
            draw.text((current_x, base_y), w, font=font, fill="white")
            
        current_x += metrics["width"] + space_width
        
    # Glow effect
    glow = img.filter(ImageFilter.GaussianBlur(radius=int(font_size*0.08)))
    glow.alpha_composite(img)
    
    arr = np.array(glow)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3] / 255.0
    
    # compatibility for moviepy 1.x and 2.x
    try:
        mask = ImageClip(alpha, is_mask=True)
    except TypeError:
        mask = ImageClip(alpha, ismask=True)
        
    clip = ImageClip(rgb)
    clip.mask = mask
    return clip

def get_spring_scale(t, duration=0.25):
    """Pop-up easing function with overshoot."""
    if t >= duration:
        return 1.0
    p = max(0.0, min(1.0, t / duration))
    return 1.0 - 0.25 * ((1.0 - p) ** 3) + 1.5 * p * ((1.0 - p) ** 2)

def apply_flicker_and_popup(clip):
    """
    Applies popup scale via cv2 resize inside transform, and flicker via alpha manipulation.
    """
    w, h = clip.size
    
    def scale_filter(get_frame, t):
        frame = get_frame(t)
        scale = get_spring_scale(t, 0.25)
        # Scale cannot be exactly 0
        scale = max(0.01, scale)
        
        if scale == 1.0:
            return frame
            
        new_w, new_h = int(w * scale), int(h * scale)
        if new_w <= 0 or new_h <= 0:
            return np.zeros_like(frame)
            
        resized_img = Image.fromarray(frame).resize((new_w, new_h), Image.Resampling.BILINEAR)
        resized = np.array(resized_img)
        
        # Pad or crop to fit original canvas size (w, h)
        canvas = np.zeros_like(frame)
        
        # Calculate offsets
        y_off = (h - new_h) // 2
        x_off = (w - new_w) // 2
        
        if scale < 1.0:
            # Place resized frame into center of canvas
            canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
        else:
            # Crop resized frame to canvas size
            crop_y = -y_off
            crop_x = -x_off
            canvas = resized[crop_y:crop_y+h, crop_x:crop_x+w]
            
        return canvas

    def opacity_filter(get_frame, t):
        frame = get_frame(t)
        if t < 0.05:
            return frame * 0.0
        elif t < 0.10:
            return frame
        elif t < 0.15:
            return frame * 0.5
        else:
            return frame

    # Use .transform which is the new moviepy 2.0+ standard, fallback to fl_image
    transform_func = getattr(clip, "transform", None)
    if transform_func is None:
        transform_func = clip.fl_image

    scaled_clip = transform_func(scale_filter)
    
    if clip.mask:
        mask_transform = getattr(clip.mask, "transform", clip.mask.fl_image)
        scaled_clip.mask = mask_transform(scale_filter)
        
        # We need to wrap the opacity filter to pass correctly
        def apply_opacity(get_frame, t):
            # First get the already scaled mask frame
            frame = get_frame(t)
            # Apply opacity logic
            if t < 0.05:
                return frame * 0.0
            elif t < 0.10:
                return frame
            elif t < 0.15:
                return frame * 0.5
            else:
                return frame

        scaled_clip.mask = mask_transform(apply_opacity, apply_to=scaled_clip.mask) if hasattr(mask_transform, 'apply_to') else scaled_clip.mask.transform(apply_opacity)
        
    return scaled_clip

def insert_starry_overrides(video_clip, audio_clip, transcript_data, font_path, trigger_keywords):
    """
    transcript_data format expected: [{"word": "selling", "start": 1.2, "end": 1.6}, ...]
    """
    width, height = video_clip.size
    
    override_clips = []
    
    for i, item in enumerate(transcript_data):
        clean_word = ''.join(e for e in item["word"] if e.isalnum()).lower()
        if clean_word in trigger_keywords:
            start_idx = max(0, i - 2)
            end_idx = min(len(transcript_data), i + 3)
            phrase_items = transcript_data[start_idx:end_idx]
            
            phrase_text = " ".join(w["word"] for w in phrase_items)
            start_time = phrase_items[0]["start"]
            end_time = phrase_items[-1]["end"]
            duration = end_time - start_time
            
            # Moviepy 2.x API
            with_start = getattr(generate_starry_background(width, height), "with_start", None)
            if with_start:
                bg_clip = generate_starry_background(width, height).with_start(start_time).with_duration(duration)
                text_clip = render_highlighted_text(phrase_text, clean_word, font_path, font_size=int(width * 0.06))
                text_clip = text_clip.with_position('center').with_start(start_time).with_duration(duration)
            else:
                # Moviepy 1.x API
                bg_clip = generate_starry_background(width, height).set_start(start_time).set_duration(duration)
                text_clip = render_highlighted_text(phrase_text, clean_word, font_path, font_size=int(width * 0.06))
                text_clip = text_clip.set_pos('center').set_start(start_time).set_duration(duration)

            animated_text = apply_flicker_and_popup(text_clip)
            
            override_clips.append(bg_clip)
            override_clips.append(animated_text)
            
    final_video = CompositeVideoClip([video_clip] + override_clips)
    
    if audio_clip:
        final_video.audio = audio_clip
        
    return final_video
