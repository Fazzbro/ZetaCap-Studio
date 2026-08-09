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

CONFIG_FILE = Path.home() / ".tiny_word_editor_pro" / "config.json"

@dataclasses.dataclass
class AppConfig:
    OPENCV_MODEL_DIR: str = get_bundled_path(os.path.join("ai_models", "opencv"), r"D:\ai_models\opencv")
    WHISPER_MODEL_DIR: str = get_bundled_path(os.path.join("ai_models", "whisper"), r"D:\ai_models\whisper")
    OUTPUT_DIR: str = os.path.join(os.path.expanduser("~"), "Documents", "ZetaCap", "Outputs")
    USER_FONTS_DIR: str = os.path.join(os.path.expanduser("~"), "Documents", "ZetaCap", "Fonts")
    TRANSITION_VIDEO_PATH: str = get_bundled_path(os.path.join("assets", "transition_landscape.mov"), r"d:\Python_Projects\captions\project\assets\transition_landscape.mov")
    GUMROAD_LICENSE_KEY: str = ""

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
        
    def get_available_fonts(self) -> List[str]:
        fonts = ['Poppins Bold', 'Sans-Serif Bold', 'Helvetica Bold', 'SF Pro Display']
        if os.path.exists(self.USER_FONTS_DIR):
            for file in os.listdir(self.USER_FONTS_DIR):
                if file.lower().endswith(('.ttf', '.otf')):
                    fonts.append(file)
        return fonts

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.OPENCV_MODEL_DIR = data.get("OPENCV_MODEL_DIR", self.OPENCV_MODEL_DIR)
                    self.WHISPER_MODEL_DIR = data.get("WHISPER_MODEL_DIR", self.WHISPER_MODEL_DIR)
                    self.GUMROAD_LICENSE_KEY = data.get("GUMROAD_LICENSE_KEY", self.GUMROAD_LICENSE_KEY)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({
                "OPENCV_MODEL_DIR": self.OPENCV_MODEL_DIR,
                "WHISPER_MODEL_DIR": self.WHISPER_MODEL_DIR,
                "GUMROAD_LICENSE_KEY": self.GUMROAD_LICENSE_KEY
            }, f, indent=4)

# Create a global configuration instance
config = AppConfig()
config.load()
config.ensure_directories()
