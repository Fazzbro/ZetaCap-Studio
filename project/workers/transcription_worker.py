import sys
from PySide6.QtCore import QThread, Signal
import whisper_timestamped as whisper
from project.core.config import config
import subprocess

# Prevent terminal popup when whisper/ffmpeg calls subprocess
if sys.platform == "win32":
    _orig_popen = subprocess.Popen
    def _patched_popen(*args, **kwargs):
        if 'creationflags' not in kwargs:
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        return _orig_popen(*args, **kwargs)
    subprocess.Popen = _patched_popen

class TranscriptionWorker(QThread):
    progress_updated = Signal(str)
    transcription_complete = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, video_path: str, model_size: str = "base"):
        super().__init__()
        self.video_path = video_path
        self.model_size = model_size

    def run(self):
        try:
            self.progress_updated.emit(f"Loading Whisper model '{self.model_size}' (Downloading if missing)...")
            model = whisper.load_model(self.model_size, download_root=config.WHISPER_MODEL_DIR)
            
            self.progress_updated.emit("Transcribing audio...")
            result = whisper.transcribe(model, self.video_path)
            
            
            self.progress_updated.emit("Parsing transcript...")
            parsed_words = []
            for segment in result.get("segments", []):
                for w in segment.get("words", []):
                    parsed_words.append({
                        "word": w.get("text", ""),
                        "start": w.get("start", 0.0),
                        "end": w.get("end", 0.0)
                    })
            
            self.progress_updated.emit("Transcription complete.")
            self.transcription_complete.emit(parsed_words)
        except Exception as e:
            import traceback
            self.error_occurred.emit(traceback.format_exc())
