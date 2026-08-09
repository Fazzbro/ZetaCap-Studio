from PySide6.QtWidgets import QMainWindow, QDockWidget, QMenuBar, QMenu, QSplitter, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox, QSlider, QSpinBox, QDoubleSpinBox, QCheckBox, QComboBox, QLineEdit, QLabel
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer

from project.ui.settings_panel import SettingsPanel
from project.ui.components import ColorButton
from project.ui.editor import EditorWidget
from project.ui.preview import PreviewWidget
from project.workers.transcription_worker import TranscriptionWorker
from project.workers.render_worker import RenderWorker, StylePreviewWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        qss = """
        QWidget {
            background-color: #0F0F0F;
            color: #e6e6e6;
        }
        QTabWidget::pane {
            border: 1px solid #1E1E1E;
        }
        QTabBar::tab {
            background: #111111;
            color: #aaa;
            padding: 8px 16px;
            border: 1px solid #1E1E1E;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background: #0F0F0F;
            color: #ffffff;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected {
            background: #1A1A1A;
        }
        QGroupBox {
            border: 1px solid #1E1E1E;
            background-color: #0F0F0F;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 5px;
            margin-bottom: 2px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 3px;
            color: #ffffff;
            font-weight: bold;
        }
        QPushButton {
            background-color: #1E1E1E;
            color: white;
            font-weight: bold;
            border: none;
            border-radius: 4px;
            padding: 4px 8px;
        }
        QPushButton:hover {
            background-color: #2A2A2A;
        }
        QPushButton:disabled {
            background-color: #0A0A0A;
            color: #555;
        }
        QPushButton[primary="true"] {
            background-color: #d97706;
            color: white;
        }
        QPushButton[primary="true"]:hover {
            background-color: #f59e0b;
        }
        QSlider::groove:horizontal {
            border: 1px solid #1E1E1E;
            background: #111111;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::sub-page:horizontal {
            background: #d97706;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::add-page:horizontal {
            background: #1E1E1E;
            height: 8px;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #f59e0b;
            border: none;
            width: 16px;
            margin-top: -4px;
            margin-bottom: -4px;
            border-radius: 8px;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #111111;
            color: white;
            border: 1px solid #1E1E1E;
            padding: 4px;
            border-radius: 3px;
        }
        QTableWidget {
            background-color: #0F0F0F;
            color: white;
            gridline-color: #1E1E1E;
            selection-background-color: #d97706;
            selection-color: white;
        }
        QHeaderView::section {
            background-color: #111111;
            color: white;
            padding: 4px;
            border: 1px solid #1E1E1E;
        }
        QScrollBar:vertical {
            background: #0F0F0F;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #1E1E1E;
            border-radius: 5px;
            min-height: 20px;
        }
        QScrollBar:horizontal {
            background: #0F0F0F;
            height: 12px;
        }
        QScrollBar::handle:horizontal {
            background: #1E1E1E;
            border-radius: 5px;
            min-width: 20px;
        }
        """
        self.setStyleSheet(qss)

        self.setup_ui()
        self.setup_connections()
        
        self.auto_preview_timer = QTimer(self)
        self.auto_preview_timer.setSingleShot(True)
        self.auto_preview_timer.setInterval(800)  # 800ms debounce
        self.auto_preview_timer.timeout.connect(self._do_auto_preview)
        
        self.mcp_sync_timer = QTimer(self)
        self.mcp_sync_timer.setInterval(500)
        self.mcp_sync_timer.timeout.connect(self._poll_mcp_sync)
        self.last_mcp_timestamp = 0.0
        self.mcp_sync_timer.start()
        
        self._hook_up_live_preview()

    def _hook_up_live_preview(self):
        for widget in self.settings.findChildren(QSlider):
            widget.valueChanged.connect(self._schedule_preview)
        for widget in self.settings.findChildren(QSpinBox):
            widget.valueChanged.connect(self._schedule_preview)
        for widget in self.settings.findChildren(QDoubleSpinBox):
            widget.valueChanged.connect(self._schedule_preview)
        for widget in self.settings.findChildren(QCheckBox):
            widget.stateChanged.connect(self._schedule_preview)
        for widget in self.settings.findChildren(QComboBox):
            widget.currentTextChanged.connect(self._schedule_preview)
        for widget in self.settings.findChildren(ColorButton):
            widget.colorChanged.connect(self._schedule_preview)
        from PySide6.QtWidgets import QLineEdit
        for widget in self.settings.findChildren(QLineEdit):
            widget.textChanged.connect(self._schedule_preview)
        
        self.settings.show_glow.stateChanged.connect(self._schedule_preview)
        self.settings.t1_glow.colorChanged.connect(self._schedule_preview)
        self.settings.t2_glow.colorChanged.connect(self._schedule_preview)
        self.settings.glow_strength.valueChanged.connect(self._schedule_preview)
        
        self.editor.table.itemChanged.connect(self._schedule_preview)
        self.editor.table.cellClicked.connect(self._on_word_clicked)
        self.preview.seek_requested.connect(self._schedule_preview)
        
    def _schedule_preview(self, *args):
        # Always allow live style preview even if no video/audio is loaded yet.
        # generate_style_preview_gui falls back to a solid color background and sample words.
        self.auto_preview_timer.start()

    def _on_word_clicked(self, row, col):
        if col in [4, 5]:
            self.settings.ensureWidgetVisible(self.settings.font_preset_dropdown)
        start_item = self.editor.table.item(row, 2)
        if start_item:
            try:
                start_time_sec = float(start_item.text())
                # Slider expects milliseconds
                self.preview.slider.setValue(int(start_time_sec * 1000))
                # Explicitly schedule preview because programmatic setValue doesn't trigger seek_requested
                self._schedule_preview()
            except ValueError:
                pass


    def reset_override(self):

        selected_rows = self.editor.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        self.editor.table.blockSignals(True)
        for idx in selected_rows:
            row = idx.row()
            if self.editor.table.item(row, 4):
                self.editor.table.item(row, 4).setText("Default")
            if self.editor.table.item(row, 5):
                self.editor.table.item(row, 5).setText("None")
        self.editor.table.blockSignals(False)
        self._schedule_preview()

    def _apply_color_to_selected(self, hex_color):
        selected_rows = self.editor.table.selectionModel().selectedRows()
        if not selected_rows: return
        self.editor.table.blockSignals(True)
        for idx in selected_rows:
            if self.editor.table.item(idx.row(), 4):
                self.editor.table.item(idx.row(), 4).setText(hex_color.upper())
        self.editor.table.blockSignals(False)
        self._schedule_preview()

    def _do_auto_preview(self):
        # Don't trigger if a render or transcription is happening
        if not self.settings.btn_render.isEnabled() or not self.settings.btn_transcribe.isEnabled():
            return
        self.start_style_preview()

    def setup_ui(self):
        from PySide6.QtWidgets import QStackedWidget
        from project.ui.prep_studio import PrepStudioWidget
        
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        # --- Screen 0: Prep Studio ---
        self.prep_studio = PrepStudioWidget()
        self.stack.addWidget(self.prep_studio)
        
        # --- Screen 1: Caption Studio (Original UI) ---
        self.caption_studio_widget = QWidget()
        caption_layout = QVBoxLayout(self.caption_studio_widget)
        caption_layout.setContentsMargins(0,0,0,0)
        
        # Top bar with a back button to return to Prep Studio
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(5,5,5,5)
        self.btn_back_to_prep = QPushButton("← Back to Video Prep")
        self.btn_back_to_prep.setFixedWidth(200)
        top_bar_layout.addWidget(self.btn_back_to_prep)
        
        self.btn_connect_claude = QPushButton("💡 Connect to Claude")
        self.btn_connect_claude.setFixedWidth(200)
        top_bar_layout.addWidget(self.btn_connect_claude)
        
        top_bar_layout.addStretch()
        caption_layout.addWidget(top_bar)
        
        splitter = QSplitter(Qt.Horizontal)

        # Left Panel (Settings)
        self.settings = SettingsPanel()
        
        self.override_warning_label = QLabel("⚠️ WORD OVERRIDE MODE: You are currently editing a single word. Global font/color changes are locked. Click 'Deselect Word(s)' below the video to return to global editing.")
        self.override_warning_label.setStyleSheet("color: white; background-color: #aa0000; padding: 6px; font-weight: bold; border-radius: 4px;")
        self.override_warning_label.setWordWrap(True)
        self.override_warning_label.hide()
        self.settings.layout().insertWidget(0, self.override_warning_label)
        
        splitter.addWidget(self.settings)

        # Right Panel (Preview & Editor)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.preview = PreviewWidget()
        self.editor = EditorWidget()
        
        right_layout.addWidget(self.preview, stretch=4)
        right_layout.addWidget(self.editor, stretch=3)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([800, 600])
        
        caption_layout.addWidget(splitter, 1)
        self.stack.addWidget(self.caption_studio_widget)

    def setup_connections(self):
        self.editor.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.editor.unselect_btn.clicked.connect(self.editor.table.clearSelection)
        self.settings.t1_top.colorChanged.connect(lambda c: self._on_override_color_changed("t1"))
        self.settings.t1_mid.colorChanged.connect(lambda c: self._on_override_color_changed("t1"))
        self.settings.t1_bot.colorChanged.connect(lambda c: self._on_override_color_changed("t1"))
        self.settings.t2_top.colorChanged.connect(lambda c: self._on_override_color_changed("t2"))
        self.settings.t2_mid.colorChanged.connect(lambda c: self._on_override_color_changed("t2"))
        self.settings.t2_bot.colorChanged.connect(lambda c: self._on_override_color_changed("t2"))
        self.settings.font_preset_dropdown.activated.connect(lambda idx: self._on_override_font_changed(self.settings.font_preset_dropdown.itemText(idx)))
        self.settings.font_preset_choice_2.activated.connect(lambda idx: self._on_override_font_changed(self.settings.font_preset_choice_2.itemText(idx)))
        self.settings.pos_offset_x.valueChanged.connect(lambda v: self._on_override_offset_changed("x", v))
        self.settings.pos_offset_y.valueChanged.connect(lambda v: self._on_override_offset_changed("y", v))
        self.settings.fonts_updated.connect(self._schedule_preview)
        self.settings.btn_browse_video.clicked.connect(self.browse_video)
        self.settings.btn_transcribe.clicked.connect(self.start_transcription)
        self.settings.btn_preview.clicked.connect(self.start_style_preview)
        self.settings.btn_render.clicked.connect(self.start_render)
        self.settings.btn_save_preset.clicked.connect(self._save_preset)
        self.settings.btn_load_preset.clicked.connect(self._load_preset)

        
        self.prep_studio.compile_finished.connect(self.on_prep_finished)
        self.prep_studio.skip_requested.connect(lambda: self.stack.setCurrentIndex(1))
        self.prep_studio.reset_requested.connect(self.on_prep_reset)
        self.btn_back_to_prep.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        self.btn_connect_claude.clicked.connect(self.setup_claude_integration)

    def on_prep_finished(self, compiled_video_path):
        self.settings.input_video.setText(compiled_video_path)
        self.preview.load_video(compiled_video_path)
        self.preview.show_video() if hasattr(self.preview, 'show_video') else None
        # Make sure toggle view is correct
        self.preview.btn_toggle_view.setChecked(True)
        self.stack.setCurrentIndex(1)
        
    def on_prep_reset(self):
        # Clear Main Studio state completely
        self.settings.input_video.clear()
        self.preview.load_video(None)
        self.editor.table.setRowCount(0)
        self.editor.words_data = []

    def _save_preset(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Zeta Project (*.zeta)")
        if not file_name:
            return
        try:
            import json, os, shutil, tempfile, uuid
            config = self.settings.get_config()
            
            # Create a temporary directory for building the archive
            temp_dir = os.path.join(tempfile.gettempdir(), f"zetacap_build_{uuid.uuid4().hex}")
            assets_dir = os.path.join(temp_dir, "assets")
            os.makedirs(assets_dir, exist_ok=True)
            
            # Helper to copy asset and update config to relative path
            def process_asset(config_key):
                asset_path = config.get(config_key)
                if asset_path and os.path.exists(asset_path) and os.path.isfile(asset_path):
                    asset_basename = os.path.basename(asset_path)
                    dest_path = os.path.join(assets_dir, asset_basename)
                    try:
                        shutil.copy2(asset_path, dest_path)
                        config[config_key] = f"assets/{asset_basename}"
                    except Exception as fe:
                        print(f"Warning: Could not bundle asset {asset_path}: {fe}")

            process_asset("font_upload")
            process_asset("font_file_2")
            process_asset("custom_roto_font_file")
            process_asset("sfx_upload_file")

            # Write project.json
            project_data = {
                "preset_name": os.path.basename(file_name),
                "settings": config
            }
            project_json_path = os.path.join(temp_dir, "project.json")
            with open(project_json_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=4)
                
            # Zip the temp directory
            # shutil.make_archive adds .zip, so we strip .zeta temporarily
            base_name = file_name
            if base_name.endswith('.zeta'):
                base_name = base_name[:-5]
            
            archive_path = shutil.make_archive(base_name, 'zip', temp_dir)
            
            # Rename .zip back to .zeta
            if archive_path.endswith('.zip') and file_name.endswith('.zeta'):
                if os.path.exists(file_name):
                    os.remove(file_name)
                os.rename(archive_path, file_name)

            # Cleanup temp dir
            try:
                shutil.rmtree(temp_dir)
            except: pass
                
            QMessageBox.information(self, "Success", f"Project saved successfully to {file_name}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to save project: {e}")

    def _load_preset(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Zeta Project (*.zeta);;JSON Files (*.json)")
        if not file_name:
            return
        try:
            import json, os, zipfile, tempfile, uuid
            
            # Handle legacy .json presets
            if file_name.endswith(".json"):
                with open(file_name, "r", encoding="utf-8") as f:
                    data = json.load(f)
                s = data.get("settings", data)
                # Legacy base64 fonts
                import base64
                embedded_fonts = data.get("embedded_fonts", {})
                if embedded_fonts:
                    temp_dir = os.path.join(tempfile.gettempdir(), "zetacap_fonts")
                    os.makedirs(temp_dir, exist_ok=True)
                    for font_name, b64_data in embedded_fonts.items():
                        font_path = os.path.join(temp_dir, font_name)
                        try:
                            with open(font_path, "wb") as font_file:
                                font_file.write(base64.b64decode(b64_data))
                            for key in ["font_upload", "font_file_2", "custom_roto_font_file"]:
                                if s.get(key) == font_name:
                                    s[key] = font_path
                        except Exception as fe:
                            pass
            else:
                # Handle new .zeta bundled archives
                extract_dir = os.path.join(tempfile.gettempdir(), f"zetacap_project_{uuid.uuid4().hex}")
                os.makedirs(extract_dir, exist_ok=True)
                
                with zipfile.ZipFile(file_name, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    
                project_json_path = os.path.join(extract_dir, "project.json")
                if not os.path.exists(project_json_path):
                    raise Exception("Invalid project file: project.json is missing.")
                    
                with open(project_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                s = data.get("settings", data)
                
                # Resolve relative asset paths to absolute extracted paths
                for key in ["font_upload", "font_file_2", "custom_roto_font_file", "sfx_upload_file"]:
                    asset_val = s.get(key)
                    if asset_val and asset_val.startswith("assets/"):
                        s[key] = os.path.join(extract_dir, asset_val)
            
            # Helper to safely set values
            def safe_set(widget, value):
                if value is None: return
                if isinstance(widget, QComboBox):
                    index = widget.findText(str(value))
                    if index >= 0: widget.setCurrentIndex(index)
                elif isinstance(widget, QSlider) or isinstance(widget, QSpinBox) or isinstance(widget, QDoubleSpinBox):
                    widget.setValue(type(widget.value())(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText(str(value))
                elif isinstance(widget, ColorButton):
                    widget.set_color(str(value))
            
            # Map settings back to UI (similar to get_config)
            safe_set(self.settings.font_preset_dropdown, s.get("font_preset_dropdown"))
            safe_set(self.settings.multi_font_mode, s.get("multi_font_mode"))
            safe_set(self.settings.font_preset_choice_2, s.get("font_preset_choice_2"))
            safe_set(self.settings.font_size_slider, s.get("font_size_slider"))
            safe_set(self.settings.bottom_font_size_slider, s.get("bottom_font_size_slider"))
            safe_set(self.settings.show_shadow, s.get("show_shadow"))
            safe_set(self.settings.shadow_depth, s.get("shadow_depth"))
            safe_set(self.settings.shadow_step_x, s.get("shadow_step_x"))
            safe_set(self.settings.shadow_step_y, s.get("shadow_step_y"))
            safe_set(self.settings.sheen_3d_scope, s.get("sheen_3d_scope"))
            safe_set(self.settings.gloss_intensity, s.get("gloss_intensity"))
            safe_set(self.settings.t1_top, s.get("t1_top"))
            safe_set(self.settings.t1_mid, s.get("t1_mid"))
            safe_set(self.settings.t1_bot, s.get("t1_bot"))
            safe_set(self.settings.t1_shadow, s.get("t1_shadow"))
            safe_set(self.settings.t2_top, s.get("t2_top"))
            safe_set(self.settings.t2_mid, s.get("t2_mid"))
            safe_set(self.settings.t2_bot, s.get("t2_bot"))
            safe_set(self.settings.t2_shadow, s.get("t2_shadow"))
            safe_set(self.settings.show_glow, s.get("show_glow"))
            safe_set(self.settings.t1_glow, s.get("t1_glow"))
            safe_set(self.settings.t2_glow, s.get("t2_glow"))
            safe_set(self.settings.glow_strength, s.get("glow_strength", 1.0))
            safe_set(self.settings.bg_box_enable, s.get("bg_box_enable", False))
            safe_set(self.settings.bg_box_color, s.get("bg_box_color", "#F5F2DA"))

            safe_set(self.settings.max_words_slider, s.get("max_words_slider"))
            safe_set(self.settings.max_chars_slider, s.get("max_chars_slider"))
            safe_set(self.settings.lines_mode_dropdown, s.get("lines_mode_dropdown"))
            safe_set(self.settings.line_spacing_scale, s.get("line_spacing_scale"))
            safe_set(self.settings.vertical_alignment, s.get("vertical_alignment"))
            safe_set(self.settings.pos_offset_x, s.get("pos_offset_x"))
            safe_set(self.settings.pos_offset_y, s.get("pos_offset_y"))
            
            safe_set(self.settings.output_mode_dropdown, s.get("output_mode_dropdown"))
            safe_set(self.settings.enable_auto_zoom, s.get("enable_auto_zoom"))
            safe_set(self.settings.zoom_factor, s.get("zoom_factor"))
            safe_set(self.settings.zoom_frequency, s.get("zoom_frequency"))
            safe_set(self.settings.zoom_transition_style, s.get("zoom_transition_style"))
            safe_set(self.settings.face_detector_model, s.get("face_detector_model"))
            safe_set(self.settings.min_cooldown_slider, s.get("min_cooldown_slider"))
            safe_set(self.settings.zoom_hold_slider, s.get("zoom_hold_slider"))
            safe_set(self.settings.enable_sfx, s.get("enable_sfx"))
            safe_set(self.settings.sfx_preset_dropdown, s.get("sfx_preset_dropdown"))
            safe_set(self.settings.sfx_upload_file, s.get("sfx_upload_file"))
            safe_set(self.settings.sfx_volume_slider, s.get("sfx_volume_slider"))
            safe_set(self.settings.sfx_trigger_mode, s.get("sfx_trigger_mode"))
            safe_set(self.settings.sfx_cooldown_slider, s.get("sfx_cooldown_slider"))
            safe_set(self.settings.rotoscope_enable, s.get("rotoscope_enable"))
            safe_set(self.settings.custom_roto_text, s.get("custom_roto_text", "CUSTOM TEXT"))
            safe_set(self.settings.custom_roto_font, s.get("custom_roto_font", "Impact"))
            safe_set(self.settings.custom_roto_font_file, s.get("custom_roto_font_file", ""))
            safe_set(self.settings.custom_roto_font_size, s.get("custom_roto_font_size", 150))
            safe_set(self.settings.custom_roto_color, s.get("custom_roto_color", "#FFFFFF"))
            safe_set(self.settings.custom_roto_show_glow, s.get("custom_roto_show_glow", False))
            safe_set(self.settings.custom_roto_glow_color, s.get("custom_roto_glow_color", "#FF7300"))
            safe_set(self.settings.custom_roto_glow_strength, s.get("custom_roto_glow_strength", 1.0))
            safe_set(self.settings.custom_roto_pos_x, s.get("custom_roto_pos_x", 0))
            safe_set(self.settings.custom_roto_pos_y, s.get("custom_roto_pos_y", 0))
            safe_set(self.settings.rotoscope_start_sec, s.get("rotoscope_start_sec"))
            safe_set(self.settings.rotoscope_end_sec, s.get("rotoscope_end_sec"))
            
            QMessageBox.information(self, "Success", f"Preset loaded successfully.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load preset: {e}")

    def browse_video(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "Select Videos", "", "Video Files (*.mp4 *.mov *.avi)")
        if file_names:
            self.settings.input_video.setText(";".join(file_names))
            self.preview.load_video(file_names[0]) # Load the first video for preview
            self.preview.show_video()

    def start_transcription(self):
        video_path = self.settings.input_video.text()
        if not video_path:
            QMessageBox.warning(self, "Error", "Please select a video file first.")
            return
            
        self.settings.btn_transcribe.setEnabled(False)
        self.settings.btn_transcribe.setText("⏳ Transcribing...")
        
        from project.ui.components import LoadingOverlay
        self.loading_overlay = LoadingOverlay("Transcribing Video...", self)
        self.loading_overlay.show()
        
        accuracy_cfg = self.settings.get_config().get("accuracy_level", "Fast")
        model_size = "tiny" if "Fast" in accuracy_cfg else "small"
        
        self.transcription_worker = TranscriptionWorker(video_path, model_size=model_size)
        self.transcription_worker.transcription_complete.connect(self.on_transcription_finished)
        self.transcription_worker.error_occurred.connect(self.on_worker_error)
        self.transcription_worker.start()

    def on_transcription_finished(self, words_table):
        from PySide6.QtWidgets import QMessageBox
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.accept()
            
        self.settings.btn_transcribe.setEnabled(True)
        self.settings.btn_transcribe.setText("🎙 Transcribe Video")
        # Populate table properly using the editor's method
        self.editor.populate_data(words_table)
        QMessageBox.information(self, "Success", "Transcription completed successfully!")

    def _get_full_config(self):
        config = self.settings.get_config()
        if getattr(self, "override_active", False) and hasattr(self, "global_settings_cache"):
            for key in ["font_preset_dropdown", "font_preset_choice_2", "t1_top", "t1_mid", "t1_bot", "t1_shadow", "t1_glow", "t2_top", "t2_mid", "t2_bot", "t2_shadow", "t2_glow", "pos_offset_x", "pos_offset_y"]:
                if self.global_settings_cache.get(key) is not None:
                    config[key] = self.global_settings_cache.get(key)
            
        words_table_list = []
        whisper_words_state_list = []
        
        for row in range(self.editor.table.rowCount()):
            id_item = self.editor.table.item(row, 0)
            word_item = self.editor.table.item(row, 1)
            start_item = self.editor.table.item(row, 2)
            end_item = self.editor.table.item(row, 3)
            color_item = self.editor.table.item(row, 4)
            font_item = self.editor.table.item(row, 5)
            x_nudge_item = self.editor.table.item(row, 6)
            y_nudge_item = self.editor.table.item(row, 7)
            
            if word_item and start_item and end_item:
                try:
                    word_id = int(id_item.text()) if id_item else row
                    word_text = word_item.text()
                    start_time = float(start_item.text())
                    end_time = float(end_item.text())
                    
                    color_override = color_item.text() if color_item else "Default"
                    font_override = font_item.text() if font_item else "None"
                    x_nudge = float(x_nudge_item.text()) if x_nudge_item and x_nudge_item.text() else 0.0
                    y_nudge = float(y_nudge_item.text()) if y_nudge_item and y_nudge_item.text() else 0.0
                    
                    row_list = [
                        word_id,            
                        word_text,          
                        font_override,             
                        x_nudge,                
                        y_nudge,                
                        color_override,     
                        "Normal (Default)"             
                    ]
                    words_table_list.append(row_list)
                    
                    whisper_words_state_list.append({
                        "text": word_text,
                        "start": start_time,
                        "end": end_time
                    })
                except ValueError:
                    pass
                    
        config['words_table'] = words_table_list
        config['whisper_words_state'] = whisper_words_state_list
        config['all_words_overrides_state'] = []
        config['preview_timestamp'] = self.preview.slider.value() / 1000.0
        return config

    def start_style_preview(self):
        self.settings.btn_preview.setEnabled(False)
        self.settings.btn_preview.setText("⏳ Generating Preview...")
        
        config = self._get_full_config()
        self.preview_worker = StylePreviewWorker(config)
        self.preview_worker.finished.connect(self.on_preview_finished)
        self.preview_worker.error.connect(self.on_worker_error)
        self.preview_worker.start()

    def on_preview_finished(self, image_path):
        self.settings.btn_preview.setEnabled(True)
        self.settings.btn_preview.setText("🔍 LIVE STYLE PREVIEW")
        if image_path:
            self.preview.show_image(image_path)

    def start_render(self):
        self.settings.btn_render.setEnabled(False)
        self.settings.btn_render.setText("⏳ Rendering...")
        
        from project.ui.components import LoadingOverlay
        self.loading_overlay = LoadingOverlay("Rendering Final Video...", self)
        self.loading_overlay.show()
        
        config = self._get_full_config()
        self.render_worker = RenderWorker(config)
        self.render_worker.finished.connect(self.on_render_finished)
        self.render_worker.error.connect(self.on_worker_error)
        self.render_worker.start()

    def on_render_finished(self, output_path):
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.accept()
            
        self.settings.btn_render.setEnabled(True)
        self.settings.btn_render.setText("🎬 Render Final Video")
        QMessageBox.information(self, "Success", f"Video rendered successfully!\nSaved to: {output_path}")

    def on_worker_error(self, error_msg):
        if hasattr(self, 'loading_overlay') and self.loading_overlay:
            self.loading_overlay.accept()
            
        self.settings.btn_transcribe.setEnabled(True)
        self.settings.btn_preview.setEnabled(True)
        self.settings.btn_render.setEnabled(True)
        self.settings.btn_transcribe.setText("🎙 Transcribe Video")
        self.settings.btn_preview.setText("🔍 LIVE STYLE PREVIEW")
        self.settings.btn_render.setText("🎬 Render Final Video")
        QMessageBox.critical(self, "Error", f"An error occurred:\n{error_msg}")

    def setup_claude_integration(self):
        import json, os, sys, glob
        from PySide6.QtWidgets import QMessageBox

        appdata = os.getenv("APPDATA")
        localappdata = os.getenv("LOCALAPPDATA")
        
        if not appdata or not localappdata:
            QMessageBox.critical(self, "Error", "Could not locate APPDATA directories.")
            return

        # 1. Standard Install Path
        claude_dir_standard = os.path.join(appdata, "Claude")
        config_path_standard = os.path.join(claude_dir_standard, "claude_desktop_config.json")
        
        # 2. Windows Store / MSIX Install Path
        claude_dir_msix = None
        config_path_msix = None
        packages_dir = os.path.join(localappdata, "Packages")
        if os.path.exists(packages_dir):
            for d in os.listdir(packages_dir):
                if d.startswith("Claude_"):
                    claude_dir_msix = os.path.join(packages_dir, d, "LocalCache", "Roaming", "Claude")
                    config_path_msix = os.path.join(claude_dir_msix, "claude_desktop_config.json")
                    break
                    
        # Determine the target path. Prefer MSIX if it exists, otherwise use standard.
        if config_path_msix and os.path.exists(config_path_msix):
            config_path = config_path_msix
            claude_dir = claude_dir_msix
        elif os.path.exists(config_path_standard):
            config_path = config_path_standard
            claude_dir = claude_dir_standard
        elif config_path_msix: # If neither exists, default to creating MSIX if we found the folder, or standard
            config_path = config_path_msix
            claude_dir = claude_dir_msix
        else:
            config_path = config_path_standard
            claude_dir = claude_dir_standard

        os.makedirs(claude_dir, exist_ok=True)

        config = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                pass

        if "mcpServers" not in config:
            config["mcpServers"] = {}

        if getattr(sys, 'frozen', False):
            # Running as compiled PyInstaller executable
            command = sys.executable
            args = ["--mcp"]
        else:
            # Running as raw python script
            command = sys.executable
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            mcp_script = os.path.join(project_root, "project", "mcp_server.py")
            args = [mcp_script]

        config["mcpServers"]["zetacap"] = {
            "command": command,
            "args": args,
            "env": {}
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            
            QMessageBox.information(self, "Integration Complete", 
                "Integration successful"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update Claude configuration:\n{e}")

    def _on_override_color_changed(self, source_type="t1"):
        if not getattr(self, "override_active", False): return
        selected_rows = self.editor.table.selectionModel().selectedRows()
        if not selected_rows: return
        
        row = selected_rows[0].row()
        
        if source_type == "t2":
            new_color = f"{self.settings.t2_top.get_color()}|{self.settings.t2_mid.get_color()}|{self.settings.t2_bot.get_color()}"
        else:
            new_color = f"{self.settings.t1_top.get_color()}|{self.settings.t1_mid.get_color()}|{self.settings.t1_bot.get_color()}"
            
        self.editor.table.blockSignals(True)
        color_item = self.editor.table.item(row, 4)
        if color_item:
            color_item.setText(new_color)
        else:
            from PySide6.QtWidgets import QTableWidgetItem
            self.editor.table.setItem(row, 4, QTableWidgetItem(new_color))
        self.editor.table.blockSignals(False)
        self._push_table_changes()

    def _on_override_font_changed(self, new_font):
        if not getattr(self, "override_active", False): return
        selected_rows = self.editor.table.selectionModel().selectedRows()
        if not selected_rows: return
        
        row = selected_rows[0].row()
        
        self.editor.table.blockSignals(True)
        font_item = self.editor.table.item(row, 5)
        if font_item:
            font_item.setText(new_font)
        else:
            from PySide6.QtWidgets import QTableWidgetItem
            self.editor.table.setItem(row, 5, QTableWidgetItem(new_font))
        
        self.editor.table.blockSignals(False)

    def _on_override_offset_changed(self, axis, value):
        if not getattr(self, "override_active", False): return
        selected_rows = self.editor.table.selectionModel().selectedRows()
        if not selected_rows: return
        
        row = selected_rows[0].row()
        col = 6 if axis == "x" else 7
        
        self.editor.table.blockSignals(True)
        item = self.editor.table.item(row, col)
        if item:
            item.setText(str(value))
        else:
            from PySide6.QtWidgets import QTableWidgetItem
            self.editor.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.editor.table.blockSignals(False)
        self._push_table_changes()

    def _on_table_selection_changed(self):
        selected_rows = self.editor.table.selectionModel().selectedRows()
        if len(selected_rows) > 0:
            if getattr(self, "override_active", False) == False:
                self.global_settings_cache = self.settings.get_config()
                self.override_active = True
                self.override_warning_label.show()
                
            row = selected_rows[0].row()
            font_item = self.editor.table.item(row, 5)
            color_item = self.editor.table.item(row, 4)
            
            font = font_item.text() if font_item and font_item.text() != "None" else self.global_settings_cache.get("font_preset_dropdown")
            color = color_item.text() if color_item and color_item.text() != "Default" else self.global_settings_cache.get("t1_top")
            
            self.settings.blockSignals(True)
            if font:
                idx = self.settings.font_preset_dropdown.findText(font)
                if idx >= 0: self.settings.font_preset_dropdown.setCurrentIndex(idx)
                idx2 = self.settings.font_preset_choice_2.findText(font)
                if idx2 >= 0: self.settings.font_preset_choice_2.setCurrentIndex(idx2)
            if color:
                if "|" in color:
                    parts = color.split("|")
                    if len(parts) == 3:
                        self.settings.t1_top.set_color(parts[0])
                        self.settings.t1_mid.set_color(parts[1])
                        self.settings.t1_bot.set_color(parts[2])
                        self.settings.t2_top.set_color(parts[0])
                        self.settings.t2_mid.set_color(parts[1])
                        self.settings.t2_bot.set_color(parts[2])
                else:
                    self.settings.t1_top.set_color(color)
                    self.settings.t1_mid.set_color(color)
                    self.settings.t1_bot.set_color(color)
                    self.settings.t2_top.set_color(color)
                    self.settings.t2_mid.set_color(color)
                    self.settings.t2_bot.set_color(color)
                    
            x_nudge_item = self.editor.table.item(row, 6)
            y_nudge_item = self.editor.table.item(row, 7)
            x_val = float(x_nudge_item.text()) if x_nudge_item and x_nudge_item.text() else self.global_settings_cache.get("pos_offset_x", 0)
            y_val = float(y_nudge_item.text()) if y_nudge_item and y_nudge_item.text() else self.global_settings_cache.get("pos_offset_y", 0)
            self.settings.pos_offset_x.setValue(int(x_val))
            self.settings.pos_offset_y.setValue(int(y_val))
            
            self.settings.blockSignals(False)
            
            self.settings.tabs.setCurrentIndex(1)
        else:
            if getattr(self, "override_active", False) == True:
                self.override_active = False
                self.override_warning_label.hide()
                self.settings.blockSignals(True)
                if hasattr(self, "global_settings_cache") and self.global_settings_cache:
                    s = self.global_settings_cache
                    idx = self.settings.font_preset_dropdown.findText(s.get("font_preset_dropdown", ""))
                    if idx >= 0: self.settings.font_preset_dropdown.setCurrentIndex(idx)
                    idx2 = self.settings.font_preset_choice_2.findText(s.get("font_preset_choice_2", ""))
                    if idx2 >= 0: self.settings.font_preset_choice_2.setCurrentIndex(idx2)
                    self.settings.t1_top.set_color(s.get("t1_top", "#FFFFFF"))
                    self.settings.t1_mid.set_color(s.get("t1_mid", "#FFFFFF"))
                    self.settings.t1_bot.set_color(s.get("t1_bot", "#FFFFFF"))
                    self.settings.t2_top.set_color(s.get("t2_top", "#FFFFFF"))
                    self.settings.t2_mid.set_color(s.get("t2_mid", "#FFFFFF"))
                    self.settings.t2_bot.set_color(s.get("t2_bot", "#FFFFFF"))
                    self.settings.pos_offset_x.setValue(s.get("pos_offset_x", 0))
                    self.settings.pos_offset_y.setValue(s.get("pos_offset_y", 0))
                self.settings.blockSignals(False)

    def _on_ai_sync_toggled(self, state):
        if state:
            self.mcp_sync_timer.start()
        else:
            self.mcp_sync_timer.stop()

    def _poll_mcp_sync(self):
        import os, json
        sync_file = os.path.join(os.path.dirname(__file__), "..", "..", "mcp_sync.json")
        if not os.path.exists(sync_file):
            return
        try:
            with open(sync_file, "r") as f:
                content = f.read().strip()
            if not content:
                return
                
            data_list = json.loads(content)
            if isinstance(data_list, dict):
                data_list = [data_list]
                
            max_ts = self.last_mcp_timestamp
            
            for data in data_list:
                try:
                    ts = data.get("timestamp", 0.0)
                    if ts <= self.last_mcp_timestamp:
                        continue
                        
                    action = data.get("action")
                    payload = data.get("payload", {})
                    
                    if action == "apply_alternating_styles":
                        self._mcp_apply_alternating_styles(payload)
                    elif action == "update_sfx_settings":
                        self._mcp_update_sfx_settings(payload)
                    elif action == "update_animation_settings":
                        self._mcp_update_animation_settings(payload)
                    elif action == "override_word_style":
                        self._mcp_override_word_style(payload)
                        
                    if ts > max_ts:
                        max_ts = ts
                except Exception as ex:
                    print(f"Error executing MCP action {data.get('action')}: {ex}")
                    
            self.last_mcp_timestamp = max_ts
                
        except Exception as e:
            print(f"MCP Sync read error: {e}")

    def _mcp_override_word_style(self, payload):
        target_word = payload.get("target_word", "").lower()
        font = payload.get("font")
        color_hex = payload.get("color_hex")
        from PySide6.QtWidgets import QTableWidgetItem
        
        if not target_word:
            return
            
        self.editor.table.blockSignals(True)
        
        # Iterate over table and find matching word(s)
        for row in range(self.editor.table.rowCount()):
            word_item = self.editor.table.item(row, 1)
            if word_item and target_word in word_item.text().lower():
                if color_hex:
                    if not self.editor.table.item(row, 4):
                        self.editor.table.setItem(row, 4, QTableWidgetItem(""))
                    self.editor.table.item(row, 4).setText(color_hex.upper())
                if font:
                    if not self.editor.table.item(row, 5):
                        self.editor.table.setItem(row, 5, QTableWidgetItem(""))
                    self.editor.table.item(row, 5).setText(font)
                    
        self.editor.table.blockSignals(False)
        self._schedule_preview()

    def _mcp_update_animation_settings(self, payload):
        pos_y = payload.get("pos_offset_y", 0)
        enable_zoom = payload.get("enable_auto_zoom", False)
        zoom_style = payload.get("zoom_transition_style", "🌊 Lush S-Curve Cinematic Glide")
        
        self.settings.blockSignals(True)
        self.settings.pos_offset_y.setValue(pos_y)
        self.settings.enable_auto_zoom.setChecked(enable_zoom)
        idx = self.settings.zoom_transition_style.findText(zoom_style)
        if idx >= 0:
            self.settings.zoom_transition_style.setCurrentIndex(idx)
        self.settings.blockSignals(False)
        self._schedule_preview()

    def _mcp_apply_alternating_styles(self, payload):
        font_1 = payload.get("font_1", "Default")
        font_2 = payload.get("font_2", "Default")
        color_1 = payload.get("color_1")
        color_2 = payload.get("color_2")
        shadow_depth = payload.get("shadow_depth", 0)
        
        self.settings.blockSignals(True)
        
        # Turn on multi-font mode
        self.settings.multi_font_mode.setCurrentText("Dual Fonts (Alternating)")
        
        # Set fonts
        idx = self.settings.font_preset_dropdown.findText(font_1)
        if idx >= 0:
            self.settings.font_preset_dropdown.setCurrentIndex(idx)
        
        idx2 = self.settings.font_preset_choice_2.findText(font_2)
        if idx2 >= 0:
            self.settings.font_preset_choice_2.setCurrentIndex(idx2)
            
        # Set colors
        if color_1:
            self.settings.t1_top.set_color(color_1)
            self.settings.t1_mid.set_color(color_1)
            self.settings.t1_bot.set_color(color_1)
        else:
            self.settings.t1_top.set_color("#FFBD59")
            self.settings.t1_mid.set_color("#FF7300")
            self.settings.t1_bot.set_color("#E53900")
            
        if color_2:
            self.settings.t2_top.set_color(color_2)
            self.settings.t2_mid.set_color(color_2)
            self.settings.t2_bot.set_color(color_2)
        else:
            self.settings.t2_top.set_color("#FFFFFF")
            self.settings.t2_mid.set_color("#FFFFFF")
            self.settings.t2_bot.set_color("#E2E8F0")
            
        # Set shadow layer
        self.settings.show_shadow.setChecked(shadow_depth > 0)
        self.settings.shadow_depth.setValue(shadow_depth)
        
        self.settings.blockSignals(False)
        self._schedule_preview()

    def _mcp_update_sfx_settings(self, payload):
        enable_sfx = payload.get("enable_sfx", True)
        sfx_preset_choice = payload.get("sfx_preset_choice")
        
        self.settings.enable_sfx.setChecked(enable_sfx)
        if sfx_preset_choice:
            idx = self.settings.sfx_preset_choice.findText(sfx_preset_choice)
            if idx >= 0:
                self.settings.sfx_preset_choice.setCurrentIndex(idx)
        self._schedule_preview()


