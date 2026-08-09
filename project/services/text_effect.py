import numpy as np
from PIL import Image, ImageFilter
from moviepy.video.VideoClip import VideoClip
import math

def smooth_spring(t: float) -> float:
    """
    Calculates a critically damped spring interpolation over time.
    """
    w = 8.0
    return 1.0 - math.exp(-w * t) * (1.0 + w * t)

class TextEffect:
    """
    An intelligent layer for rendering dynamic, physics-based text animations 
    using pre-rendered styled frames from ZetaCap's engine.
    
    This effectively "slices" the pre-rendered clip into overlapping characters
    and staggers them with physics.
    """
    
    def __init__(
        self,
        clip: VideoClip,
        text: str,
        font,
        pad: int = 40,
        tracking: int = -4,
        preset: str = 'fade-in-blur',
        per: str = 'char',
        speed_reveal: float = 1.1,
        speed_segment: float = 0.3
    ):
        self.text = text
        self.preset = preset
        self.per = per
        self.speed_reveal = float(speed_reveal)
        self.speed_segment = float(speed_segment)
        self.pad = pad
        
        self.stagger_step = 0.15 / (self.speed_reveal if self.speed_reveal > 0 else 1.0)
        self.segment_duration = 0.7 / (self.speed_segment if self.speed_segment > 0 else 1.0)
        
        self._last_t = None
        self._last_frame = None
        
        # Get the first frame (since it's a static styled clip)
        clip_frame = clip.get_frame(0)
        
        # If the clip has a mask, combine them into an RGBA PIL Image
        rgb = Image.fromarray(clip_frame)
        if clip.mask is not None:
            clip_mask = clip.mask.get_frame(0)
            alpha = Image.fromarray((clip_mask * 255).astype(np.uint8), mode='L')
        else:
            alpha = Image.new('L', rgb.size, 255)
            
        self.full_img = rgb.convert("RGBA")
        self.full_img.putalpha(alpha)
        
        self.width = self.full_img.width
        self.height = self.full_img.height
        
        # Generate vertical slices for each character/word
        self.slices = []
        if self.per == 'word':
            words = self.text.split(' ')
            cursor_x = pad
            midpoints = [0]
            for i, word in enumerate(words):
                try:
                    adv = font.getlength(word)
                except Exception:
                    adv = font.getbbox(word)[2] if font.getbbox(word) else 20
                    
                cursor_x += adv
                if i < len(words) - 1:
                    try:
                        space_adv = font.getlength(' ')
                    except Exception:
                        space_adv = 10
                    midpoints.append(int(cursor_x + (space_adv + tracking) / 2.0))
                    cursor_x += space_adv + tracking
                else:
                    midpoints.append(self.width)
                    
            for i in range(len(words)):
                slice_x1 = max(0, midpoints[i])
                slice_x2 = min(self.width, midpoints[i+1])
                
                if slice_x2 > slice_x1:
                    word_img = self.full_img.crop((slice_x1, 0, slice_x2, self.height))
                    self.slices.append((slice_x1, word_img))
        else:
            cursor_x = pad
            # Calculate precise slice midpoints to avoid alpha double-blending
            midpoints = [0]
            for i, ch in enumerate(self.text):
                try:
                    adv = font.getlength(ch)
                except Exception:
                    adv = font.getbbox(ch)[2] if font.getbbox(ch) else 20
                    
                cursor_x += adv
                if i < len(self.text) - 1:
                    midpoints.append(int(cursor_x + tracking / 2.0))
                    cursor_x += tracking
                else:
                    midpoints.append(self.width)
                    
            for i in range(len(self.text)):
                slice_x1 = max(0, midpoints[i])
                slice_x2 = min(self.width, midpoints[i+1])
                
                if slice_x2 > slice_x1:
                    char_img = self.full_img.crop((slice_x1, 0, slice_x2, self.height))
                    self.slices.append((slice_x1, char_img))

    def make_frame(self, t: float) -> np.ndarray:
        # Cache hit check to avoid 2x rendering (RGB and Mask clips call this with the same t consecutively)
        if self._last_t == t and self._last_frame is not None:
            return self._last_frame

        # Create transparent canvas matching the exact size of the original styled clip
        
        # Optimization: If all animations are finished, return the flawless original image
        all_settled = True
        for i in range(len(self.slices)):
            if (t - i * self.stagger_step) < self.segment_duration:
                all_settled = False
                break
        
        if all_settled:
            res = np.array(self.full_img)
            self._last_t = t
            self._last_frame = res
            return res
            
        frame = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        
        global_fade_time = min(0.2, self.segment_duration * 0.5)
        global_opacity = min(1.0, t / global_fade_time) if global_fade_time > 0 else 1.0
        
        for i, (paste_x, char_img) in enumerate(self.slices):
            char_start_time = i * self.stagger_step
            local_t = t - char_start_time
            
            if local_t <= 0:
                progress = 0
            elif local_t >= self.segment_duration:
                progress = 1
            else:
                progress = smooth_spring(local_t / self.segment_duration)
                
            opacity = 255
            blur_radius = 0
            y_offset = 0
            
            if self.preset == 'fade-in-blur':
                blur_radius = max(0, 20 * (1 - progress))
                y_offset = 40 * (1 - progress)
                opacity = int(255 * global_opacity)
            elif self.preset == 'slide':
                y_offset = 40 * (1 - progress)
                opacity = int(255 * progress)
            
            opacity = max(0, min(255, opacity))
            
            if opacity > 0:
                working_img = char_img.copy()
                
                # Apply per-character opacity if not fully opaque using highly-optimized LUT
                if opacity < 255:
                    alpha_lut = [int(p * (opacity / 255.0)) for p in range(256)]
                    alpha = working_img.getchannel('A').point(alpha_lut)
                    working_img.putalpha(alpha)
                    
                if blur_radius > 0:
                    working_img = working_img.filter(ImageFilter.GaussianBlur(blur_radius))
                    
                paste_y = int(y_offset)
                frame.alpha_composite(working_img, (paste_x, paste_y))
                
        res = np.array(frame)
        self._last_t = t
        self._last_frame = res
        return res
