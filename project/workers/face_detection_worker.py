from PySide6.QtCore import QThread, Signal
from project.services.video_service import detect_face_centers_for_intervals

class FaceDetectionWorker(QThread):
    progress_updated = Signal(str)
    detection_complete = Signal(list)
    error_occurred = Signal(str)

    def __init__(self, video_path: str, intervals: list, model_choice: str, canvas_w: int, canvas_h: int):
        super().__init__()
        self.video_path = video_path
        self.intervals = intervals
        self.model_choice = model_choice
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

    def run(self):
        try:
            self.progress_updated.emit("Running face detection...")
            results = detect_face_centers_for_intervals(
                self.video_path, self.intervals, self.model_choice, self.canvas_w, self.canvas_h
            )
            self.detection_complete.emit(results)
        except Exception as e:
            self.error_occurred.emit(str(e))
