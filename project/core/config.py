import os
import json
import dataclasses
from typing import Optional, List, Dict
from pathlib import Path

import sys

def get_bundled_path(relative_path: str, fallback_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return fallback_path

ZETACAP_CONFIG_DIR = Path.home() / ".zetacap"
LEGACY_CONFIG_DIR = Path.home() / ".tiny_word_editor_pro"

CONFIG_FILE = ZETACAP_CONFIG_DIR / "config.json"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "config.json"

@dataclasses.dataclass
class AppConfig:
    OPENCV_MODEL_DIR: str = get_bundled_path(os.path.join("ai_models", "opencv"), r"D:\ai_models\opencv")
    WHISPER_MODEL_DIR: str = get_bundled_path(os.path.join("ai_models", "whisper"), r"D:\ai_models\whisper")
    OUTPUT_DIR: str = os.path.join(os.path.expanduser("~"), "Documents", "ZetaCap", "Outputs")
    USER_FONTS_DIR: str = os.path.join(os.path.expanduser("~"), "Documents", "ZetaCap", "Fonts")
    TRANSITION_VIDEO_PATH: str = get_bundled_path(os.path.join("assets", "transition_landscape.mov"), r"d:\Python_Projects\captions\project\assets\transition_landscape.mov")
    PRESETS_DIR: str = get_bundled_path("presets", r"d:\Python_Projects\captions\presets")
    GUMROAD_LICENSE_KEY: str = ""
    ACTIVATED_HWID: str = ""

    @property
    def YUNET_MODEL_PATH(self) -> str:
        return os.path.join(self.OPENCV_MODEL_DIR, "face_detection_yunet_2023mar.onnx")
        
    @property
    def HAAR_MODEL_PATH(self) -> str:
        return os.path.join(self.OPENCV_MODEL_DIR, "haarcascade_frontalface_default.xml")
        
    def ensure_directories(self):
        os.makedirs(self.OPENCV_MODEL_DIR, exist_ok=True)
        os.makedirs(self.WHISPER_MODEL_DIR, exist_ok=True)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.USER_FONTS_DIR, exist_ok=True)
        os.makedirs(ZETACAP_CONFIG_DIR, exist_ok=True)
        
    def get_available_fonts(self) -> List[str]:
        fonts = ['Poppins Bold', 'Sans-Serif Bold', 'Helvetica Bold', 'SF Pro Display']
        if os.path.exists(self.USER_FONTS_DIR):
            for file in os.listdir(self.USER_FONTS_DIR):
                if file.lower().endswith(('.ttf', '.otf')):
                    fonts.append(file)
        return fonts

    def load(self):
        target_file = None
        if CONFIG_FILE.exists():
            target_file = CONFIG_FILE
        elif LEGACY_CONFIG_FILE.exists():
            target_file = LEGACY_CONFIG_FILE

        if target_file and target_file.exists():
            try:
                with open(target_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Only override model paths if NOT bundled, or if the user explicitly set a custom path that exists
                    is_bundled = hasattr(sys, '_MEIPASS')
                    
                    saved_opencv = data.get("OPENCV_MODEL_DIR")
                    if saved_opencv and (not is_bundled or os.path.exists(saved_opencv)):
                        # If bundled, only accept if it actually exists (so old D:\\ paths don't break it)
                        if not is_bundled or (saved_opencv != r"D:\ai_models\opencv" and os.path.exists(saved_opencv)):
                            self.OPENCV_MODEL_DIR = saved_opencv
                            
                    saved_whisper = data.get("WHISPER_MODEL_DIR")
                    if saved_whisper and (not is_bundled or os.path.exists(saved_whisper)):
                        if not is_bundled or (saved_whisper != r"D:\ai_models\whisper" and os.path.exists(saved_whisper)):
                            self.WHISPER_MODEL_DIR = saved_whisper
                            
                    self.GUMROAD_LICENSE_KEY = data.get("GUMROAD_LICENSE_KEY", self.GUMROAD_LICENSE_KEY)
                    self.ACTIVATED_HWID = data.get("ACTIVATED_HWID", self.ACTIVATED_HWID)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "OPENCV_MODEL_DIR": self.OPENCV_MODEL_DIR,
                "WHISPER_MODEL_DIR": self.WHISPER_MODEL_DIR,
                "GUMROAD_LICENSE_KEY": self.GUMROAD_LICENSE_KEY,
                "ACTIVATED_HWID": self.ACTIVATED_HWID
            }, f, indent=4)

# Create a global configuration instance
config = AppConfig()
config.load()
config.ensure_directories()
