from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QComboBox, QSlider, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt

class SilenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto-Cut Settings")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Info Label
        info = QLabel(
            "Automatically remove dead air and silences from your video.\\n"
            "The cuts will be added to your segments list non-destructively."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Settings Group
        group = QGroupBox("Detection Engine")
        form = QFormLayout(group)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Vlog Mode (Volume-Based, Safe for Unboxings)",
            "Podcast Mode (AI Word-Based, Aggressive)"
        ])
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)
        form.addRow("Mode:", self.mode_combo)
        
        # Aggression Slider (Only for Volume Mode)
        self.slider_layout = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(-50, -10)
        self.slider.setValue(-35) # Default safe threshold
        
        self.lbl_slider_val = QLabel("-35 dB")
        self.slider.valueChanged.connect(lambda v: self.lbl_slider_val.setText(f"{v} dB"))
        
        self.slider_layout.addWidget(self.slider)
        self.slider_layout.addWidget(self.lbl_slider_val)
        
        form.addRow("Aggression:", self.slider_layout)
        
        layout.addWidget(group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Cut Silences")
        self.btn_run.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_run)
        
        layout.addLayout(btn_layout)
        
    def on_mode_changed(self, index):
        # Disable slider if using Whisper (Podcast mode)
        is_volume = (index == 0)
        self.slider.setEnabled(is_volume)
        
    def get_settings(self):
        return {
            "mode": "vlog" if self.mode_combo.currentIndex() == 0 else "podcast",
            "aggression": self.slider.value()
        }
