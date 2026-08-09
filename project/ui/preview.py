from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QStackedWidget
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget

class PreviewWidget(QWidget):
    seek_requested = Signal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        self.stack = QStackedWidget()
        
        # Video Player Widget
        self.video_widget = QVideoWidget()
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        
        # Image Preview Widget
        self.image_label = QLabel("Live Style Preview")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #0F0F0F; color: #ffffff; font-size: 16px;")
        
        self.stack.addWidget(self.video_widget)
        self.stack.addWidget(self.image_label)
        layout.addWidget(self.stack)
        
        # Controls Layout
        self.controls_layout = QHBoxLayout()
        
        self.btn_toggle_view = QPushButton("Show Raw Video")
        self.btn_toggle_view.setCheckable(True)
        
        self.btn_play = QPushButton("Play")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        
        self.time_label = QLabel("00:00.00")
        
        self.controls_layout.addWidget(self.btn_toggle_view)
        self.controls_layout.addWidget(self.btn_play)
        self.controls_layout.addWidget(self.slider)
        self.controls_layout.addWidget(self.time_label)
        
        layout.addLayout(self.controls_layout)
        
        # Connections
        self.btn_toggle_view.toggled.connect(self._on_toggle_view)
        self.btn_play.clicked.connect(self._on_play_clicked)
        self.player.positionChanged.connect(self._on_position_changed)
        self.player.durationChanged.connect(self._on_duration_changed)
        
        # State variables
        self.is_scrubbing = False
        
        self.slider.sliderPressed.connect(self._slider_pressed)
        self.slider.sliderReleased.connect(self._slider_released)

        # Default State
        self.show_image_mode()

    def _slider_pressed(self):
        self.is_scrubbing = True
        
    def _slider_released(self):
        self.is_scrubbing = False
        self.player.setPosition(self.slider.value())
        self.seek_requested.emit(self.slider.value())

    def _on_toggle_view(self, checked):
        if checked:
            self.btn_toggle_view.setText("Show Styled Preview")
            self.stack.setCurrentIndex(0) # Raw Video
        else:
            self.btn_toggle_view.setText("Show Raw Video")
            self.stack.setCurrentIndex(1) # Image Preview
            self.player.pause()
            self.btn_play.setText("Play")

    def _on_play_clicked(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.btn_play.setText("Play")
        else:
            # Force switch to video view if they hit play!
            if not self.btn_toggle_view.isChecked():
                self.btn_toggle_view.setChecked(True)
            self.player.play()
            self.btn_play.setText("Pause")

    def _on_position_changed(self, position):
        if not self.is_scrubbing:
            self.slider.setValue(position)
        self._update_time_label(position)
            
    def _on_duration_changed(self, duration):
        self.slider.setRange(0, duration)

    def _update_time_label(self, position):
        s = position / 1000.0
        m = int(s // 60)
        s = s % 60
        self.time_label.setText(f"{m:02d}:{s:05.2f}")

    def load_video(self, file_path):
        if not file_path:
            self.player.setSource(QUrl())
        else:
            self.player.setSource(QUrl.fromLocalFile(file_path))
        self.player.pause()
        self.btn_play.setText("Play")

    def show_image_mode(self):
        self.btn_toggle_view.setChecked(False)

    def show_image(self, image_path):
        # We don't force switch back, just update the pixmap.
        # If they are in video mode, they won't see it until they toggle back.
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
