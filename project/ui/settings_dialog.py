from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                               QLabel, QLineEdit, QPushButton, QFileDialog, QMessageBox)
from project.core.config import config

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(500, 200)
        
        layout = QVBoxLayout(self)
        
        # OpenCV Model Dir
        cv_layout = QHBoxLayout()
        cv_label = QLabel("OpenCV Models Directory:")
        self.cv_input = QLineEdit(config.OPENCV_MODEL_DIR)
        cv_btn = QPushButton("Browse...")
        cv_btn.clicked.connect(self.browse_cv_dir)
        cv_layout.addWidget(cv_label)
        cv_layout.addWidget(self.cv_input)
        cv_layout.addWidget(cv_btn)
        layout.addLayout(cv_layout)
        
        # Whisper Model Dir
        whisper_layout = QHBoxLayout()
        whisper_label = QLabel("Whisper Models Directory:")
        self.whisper_input = QLineEdit(config.WHISPER_MODEL_DIR)
        whisper_btn = QPushButton("Browse...")
        whisper_btn.clicked.connect(self.browse_whisper_dir)
        whisper_layout.addWidget(whisper_label)
        whisper_layout.addWidget(self.whisper_input)
        whisper_layout.addWidget(whisper_btn)
        layout.addLayout(whisper_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
    def browse_cv_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select OpenCV Models Directory", self.cv_input.text())
        if dir_path:
            self.cv_input.setText(dir_path)
            
    def browse_whisper_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Whisper Models Directory", self.whisper_input.text())
        if dir_path:
            self.whisper_input.setText(dir_path)
            
    def save_settings(self):
        config.OPENCV_MODEL_DIR = self.cv_input.text()
        config.WHISPER_MODEL_DIR = self.whisper_input.text()
        try:
            config.save()
            config.ensure_directories()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save settings: {e}")
