from PySide6.QtCore import QThread, Signal
from project.services.silence_service import get_volume_segments, get_whisper_segments

class SilenceWorker(QThread):
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, filepath, mode="vlog", aggression=-35):
        super().__init__()
        self.filepath = filepath
        self.mode = mode
        self.aggression = aggression

    def run(self):
        try:
            if self.mode == "vlog":
                # Safe mode: FFmpeg volume detection
                segments = get_volume_segments(self.filepath, noise_db=self.aggression, min_dur=0.5)
            else:
                # Podcast mode: Whisper AI word detection
                segments = get_whisper_segments(self.filepath, padding=0.3)
                
            self.finished.emit(segments)
        except Exception as e:
            self.error.emit(str(e))
