import os
import subprocess
from PySide6.QtCore import QThread, Signal
import imageio_ffmpeg
from moviepy import VideoFileClip
import cv2

class PrepWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, video_configs, music_path=None, music_volume=0.5):
        super().__init__()
        self.video_configs = video_configs
        self.music_path = music_path
        self.music_volume = music_volume

    def run(self):
        try:
            from project.services.compile_service import compile_video_sync
            output_path = compile_video_sync(self.video_configs, self.music_path, self.music_volume)
            self.finished.emit(output_path)
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))
