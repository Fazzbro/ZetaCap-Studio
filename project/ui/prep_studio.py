import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QFileDialog, QListWidget, QListWidgetItem, QSlider, QSpinBox, 
    QDoubleSpinBox, QGroupBox, QScrollArea, QFrame, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from project.ui.preview import PreviewWidget
from project.workers.prep_worker import PrepWorker
from moviepy import VideoFileClip

class VideoTrimItem(QWidget):
    preview_requested = Signal(str)
    seek_requested = Signal(float)

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.duration = self._get_duration()
        self.segments = [(0.0, self.duration)]
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Top Row
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        self.name_label = QLabel(os.path.basename(filepath))
        self.name_label.setStyleSheet("font-weight: bold;")
        
        self.btn_preview = QPushButton("Preview")
        self.btn_preview.clicked.connect(lambda: self.preview_requested.emit(self.filepath))
        
        top_layout.addWidget(self.name_label)
        top_layout.addWidget(self.btn_preview)
        top_layout.addStretch()
        
        layout.addWidget(top_row)
        
        # Segments List
        self.segments_list = QListWidget()
        self.segments_list.setMinimumHeight(150)
        self.segments_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.segments_list.itemClicked.connect(self.on_segment_clicked)
        layout.addWidget(self.segments_list)
        
        # Delete Button
        self.btn_del_seg = QPushButton("🗑 Delete Selected Segment")
        self.btn_del_seg.clicked.connect(self.delete_selected_segment)
        layout.addWidget(self.btn_del_seg)
        
        self.refresh_list()
        
    def on_segment_clicked(self, item):
        row = self.segments_list.row(item)
        if row >= 0 and row < len(self.segments):
            start_time = self.segments[row][0]
            self.seek_requested.emit(start_time)

    def _get_duration(self):
        try:
            with VideoFileClip(self.filepath) as c:
                return c.duration
        except:
            return 9999.0

    def refresh_list(self):
        self.segments_list.clear()
        for i, (s, e) in enumerate(self.segments):
            self.segments_list.addItem(f"Clip {i+1}: {s:.2f}s to {e:.2f}s")
            
    def delete_selected_segment(self):
        row = self.segments_list.currentRow()
        if row >= 0 and row < len(self.segments):
            if len(self.segments) == 1:
                QMessageBox.warning(self, "Warning", "Cannot delete the only segment. Remove the video instead.")
                return
            self.segments.pop(row)
            self.refresh_list()
            
    def split_at(self, t):
        # Find which segment this timestamp falls into
        for i, (s, e) in enumerate(self.segments):
            if s < t < e:
                # Split this segment!
                self.segments.pop(i)
                self.segments.insert(i, (t, e))
                self.segments.insert(i, (s, t))
                self.refresh_list()
                return True
        return False
        
    def get_configs(self):
        # Returns a list of configs for this video
        configs = []
        for (s, e) in self.segments:
            configs.append({
                'path': self.filepath,
                'start': s,
                'end': e
            })
        return configs


class PrepStudioWidget(QWidget):
    compile_finished = Signal(str)
    skip_requested = Signal()
    reset_requested = Signal()

    def __init__(self):
        super().__init__()
        self.music_path = None
        self.active_video_item = None
        
        main_layout = QHBoxLayout(self)
        
        # Left Panel (Controls)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignTop)
        
        # Top Buttons
        top_buttons = QHBoxLayout()
        self.btn_add_videos = QPushButton("➕ Add Videos")
        self.btn_add_videos.clicked.connect(self.add_videos)
        top_buttons.addWidget(self.btn_add_videos)
        
        self.btn_reset = QPushButton("🗑 Start Over")
        self.btn_reset.clicked.connect(self.reset_studio)
        top_buttons.addWidget(self.btn_reset)
        
        self.btn_skip = QPushButton("→ Skip to Captions")
        self.btn_skip.clicked.connect(self.skip_requested.emit)
        top_buttons.addWidget(self.btn_skip)
        
        left_layout.addLayout(top_buttons)
        
        # Video List
        self.video_list_area = QScrollArea()
        self.video_list_area.setWidgetResizable(True)
        self.video_list_container = QWidget()
        self.video_list_layout = QVBoxLayout(self.video_list_container)
        self.video_list_layout.setAlignment(Qt.AlignTop)
        self.video_list_area.setWidget(self.video_list_container)
        left_layout.addWidget(self.video_list_area)
        
        # Music Controls
        music_group = QGroupBox("Background Music")
        music_layout = QVBoxLayout(music_group)
        
        self.lbl_music = QLabel("No music selected")
        self.btn_add_music = QPushButton("🎵 Select Music")
        self.btn_add_music.clicked.connect(self.add_music)
        
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Volume:"))
        self.music_vol_slider = QSlider(Qt.Horizontal)
        self.music_vol_slider.setRange(0, 100)
        self.music_vol_slider.setValue(50)
        vol_layout.addWidget(self.music_vol_slider)
        
        music_layout.addWidget(self.lbl_music)
        music_layout.addWidget(self.btn_add_music)
        music_layout.addLayout(vol_layout)
        left_layout.addWidget(music_group)
        
        # Compile Button
        self.btn_compile = QPushButton("⚡ Compile & Proceed to Captions")
        self.btn_compile.setProperty("primary", True)
        self.btn_compile.setMinimumHeight(50)
        self.btn_compile.clicked.connect(self.start_compile)
        left_layout.addWidget(self.btn_compile)
        
        # Right Panel (Preview)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.preview = PreviewWidget()
        
        # Split Tool
        self.btn_split = QPushButton("✂ Split at Playhead")
        self.btn_split.setMinimumHeight(40)
        self.btn_split.clicked.connect(self.split_active_video)
        
        # Auto-Cut Tool
        self.btn_autocut = QPushButton("⚡ Auto-Cut Silences")
        self.btn_autocut.setMinimumHeight(40)
        self.btn_autocut.clicked.connect(self.start_autocut)
        
        right_layout.addWidget(self.preview)
        right_layout.addWidget(self.btn_split)
        right_layout.addWidget(self.btn_autocut)
        
        main_layout.addWidget(left_panel, stretch=1)
        main_layout.addWidget(right_panel, stretch=2)
        
        self.video_items = []
        self.silence_worker = None

    def add_videos(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.mov *.avi)")
        for f in file_names:
            item = VideoTrimItem(f)
            item.preview_requested.connect(self.preview_video)
            item.seek_requested.connect(self.seek_preview)
            self.video_list_layout.addWidget(item)
            self.video_items.append(item)
            
            if len(self.video_items) == 1:
                self.preview_video(f)

    def seek_preview(self, position_sec):
        if self.preview.player:
            self.preview.btn_toggle_view.setChecked(True)
            self.preview.player.setPosition(int(position_sec * 1000))
            self.preview.player.play()
            self.preview.btn_play.setText("Pause")

    def add_music(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Music", "", "Audio Files (*.mp3 *.wav)")
        if file_name:
            self.music_path = file_name
            self.lbl_music.setText(os.path.basename(file_name))

    def reset_studio(self):
        self.preview.player.stop()
        self.preview.load_video(None)
        
        while self.video_list_layout.count():
            item = self.video_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
                
        self.video_items.clear()
        self.active_video_item = None
        
        self.music_path = None
        self.lbl_music.setText("No music selected")
        self.music_vol_slider.setValue(50)
        
        self.reset_requested.emit()

    def preview_video(self, filepath):
        for item in self.video_items:
            if item.filepath == filepath:
                self.active_video_item = item
                break
                
        self.preview.load_video(filepath)
        self.preview.btn_toggle_view.setChecked(True)
        self.preview.player.play()
        self.preview.btn_play.setText("Pause")

    def split_active_video(self):
        if not self.active_video_item:
            QMessageBox.warning(self, "Error", "Select a video to preview first!")
            return
            
        t = self.preview.player.position() / 1000.0 # ms to seconds
        success = self.active_video_item.split_at(t)
        if not success:
            QMessageBox.warning(self, "Error", f"Timestamp {t:.2f}s is not within any active segment!")

    def start_autocut(self):
        if not self.active_video_item:
            QMessageBox.warning(self, "Error", "Select a video to preview first!")
            return
            
        from project.ui.silence_dialog import SilenceDialog
        dialog = SilenceDialog(self)
        if dialog.exec():
            settings = dialog.get_settings()
            
            self.btn_autocut.setEnabled(False)
            self.btn_autocut.setText("⏳ Analyzing Video...")
            
            from project.workers.silence_worker import SilenceWorker
            self.silence_worker = SilenceWorker(
                self.active_video_item.filepath,
                mode=settings["mode"],
                aggression=settings["aggression"]
            )
            self.silence_worker.finished.connect(self.on_autocut_finished)
            self.silence_worker.error.connect(self.on_autocut_error)
            self.silence_worker.start()

    def on_autocut_finished(self, segments):
        self.btn_autocut.setEnabled(True)
        self.btn_autocut.setText("⚡ Auto-Cut Silences")
        
        if not segments:
            QMessageBox.information(self, "Auto-Cut", "Video appears to be entirely silent!")
            return
            
        if self.active_video_item:
            self.active_video_item.segments = segments
            self.active_video_item.refresh_list()
            QMessageBox.information(self, "Success", f"Automatically detected {len(segments)} active segments!")

    def on_autocut_error(self, err):
        self.btn_autocut.setEnabled(True)
        self.btn_autocut.setText("⚡ Auto-Cut Silences")
        QMessageBox.critical(self, "Error", f"Auto-Cut Failed:\n{err}")

    def start_compile(self):
        if not self.video_items:
            QMessageBox.warning(self, "Error", "Please add at least one video to compile.")
            return
            
        configs = []
        for item in self.video_items:
            configs.extend(item.get_configs())
            
        if not configs:
            QMessageBox.warning(self, "Error", "No active segments found!")
            return
            
        music_vol = self.music_vol_slider.value() / 100.0
        
        self.btn_compile.setEnabled(False)
        self.btn_compile.setText("⏳ Compiling Master Video...")
        
        from project.ui.components import LoadingOverlay
        self.loading_overlay = LoadingOverlay("Compiling Master Video...", self)
        self.loading_overlay.show()
        
        self.worker = PrepWorker(configs, self.music_path, music_vol)
        self.worker.finished.connect(self.on_compile_finished)
        self.worker.error.connect(self.on_compile_error)
        self.worker.start()
        
    def on_compile_finished(self, final_path):
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.accept()
            
        self.btn_compile.setEnabled(True)
        self.btn_compile.setText("⚡ Compile & Proceed to Captions")
        self.compile_finished.emit(final_path)
        
    def on_compile_error(self, err):
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.accept()
            
        self.btn_compile.setEnabled(True)
        self.btn_compile.setText("⚡ Compile & Proceed to Captions")
        QMessageBox.critical(self, "Error", f"Failed to compile video:\n{err}")
