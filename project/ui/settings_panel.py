from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QScrollArea, QGroupBox, 
                               QFormLayout, QCheckBox, QLineEdit, QPushButton, QComboBox, QSlider, QSpinBox, QDoubleSpinBox, QLabel,
                               QTabBar, QStylePainter, QStyleOptionTab, QStyle)
from PySide6.QtCore import Qt, QSize
from project.ui.components import ColorButton

from PySide6.QtGui import QPainter

class HorizontalTabBar(QTabBar):
    def tabSizeHint(self, index):
        size = super().tabSizeHint(index)
        return QSize(max(120, size.height()), max(40, size.width()))

    def paintEvent(self, event):
        painter = QStylePainter(self)
        option = QStyleOptionTab()
        for index in range(self.count()):
            self.initStyleOption(option, index)
            text = option.text
            option.text = ""
            painter.drawControl(QStyle.CE_TabBarTab, option)
            
        p = QPainter(self)
        p.setPen(self.palette().windowText().color())
        for index in range(self.count()):
            self.initStyleOption(option, index)
            p.drawText(self.tabRect(index), Qt.AlignCenter | Qt.AlignVCenter, option.text)

class SettingsPanel(QWidget):
    from PySide6.QtCore import Signal
    fonts_updated = Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setTabBar(HorizontalTabBar())
        self.tabs.setTabPosition(QTabWidget.West)
        layout.addWidget(self.tabs)

        preset_group = QGroupBox("Presets")
        preset_layout = QVBoxLayout()
        preset_buttons_layout = QHBoxLayout()
        self.btn_save_preset = QPushButton("💾 SAVE PROJECT (.zeta)")
        self.btn_load_preset = QPushButton("🚀 LOAD PROJECT (.zeta)")
        preset_buttons_layout.addWidget(self.btn_save_preset)
        preset_buttons_layout.addWidget(self.btn_load_preset)
        preset_layout.addLayout(preset_buttons_layout)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)
        

        self.setup_tabs()

    def create_scrollable_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        scroll.setWidget(container)
        return scroll, layout

    def _create_slider(self, min_val, max_val, default_val):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_val, max_val)
        s.setValue(default_val)
        return s

    def _create_double_spinbox(self, min_val, max_val, step, default_val):
        sb = QDoubleSpinBox()
        sb.setRange(min_val, max_val)
        sb.setSingleStep(step)
        sb.setValue(default_val)
        return sb

    def setup_tabs(self):
        # 1. Media
        t0, l0 = self.create_scrollable_tab()
        self.tabs.addTab(t0, 'Media')
        
        g1 = QGroupBox('Video/Audio Sources')
        fl1 = QFormLayout(g1)
        self.input_video = QLineEdit()
        self.btn_browse_video = QPushButton("Browse Video...")
        video_layout = QHBoxLayout()
        video_layout.addWidget(self.input_video)
        video_layout.addWidget(self.btn_browse_video)
        
        self.input_audio = QLineEdit()
        self.audio_aspect = QComboBox()
        self.audio_aspect.addItems(["9:16 (TikTok/Reels)", "16:9 (YouTube)", "1:1 (Square)"])
        
        self.accuracy_level = QComboBox()
        self.accuracy_level.addItems(["Fast (Default)", "High Accuracy (Requires Background Download)"])
        
        self.output_mode_dropdown = QComboBox()
        self.output_mode_dropdown.addItems(["Burn directly into original video", "Green Screen Matte (Only Captions on #00FF00)"])
        
        fl1.addRow('Source Video:', video_layout)
        fl1.addRow('Source Audio (optional):', self.input_audio)
        fl1.addRow('Audio-only Aspect:', self.audio_aspect)
        fl1.addRow('Accuracy Level:', self.accuracy_level)
        fl1.addRow('Output Mode:', self.output_mode_dropdown)
        l0.addWidget(g1)
        
        g_actions = QGroupBox('Actions')
        fl_actions = QVBoxLayout(g_actions)
        self.btn_transcribe = QPushButton("🎙 Transcribe Video")
        self.btn_preview = QPushButton("Live Style Preview")
        self.btn_render = QPushButton("🎬 Render Final Video")
        self.btn_render.setProperty("primary", True)
        fl_actions.addWidget(self.btn_transcribe)
        fl_actions.addWidget(self.btn_preview)
        fl_actions.addWidget(self.btn_render)
        l0.addWidget(g_actions)
        l0.addStretch()

        # 2. Typography
        t1, l1 = self.create_scrollable_tab()
        self.tabs.addTab(t1, 'Typography')
        g2 = QGroupBox('Font & Spacing')
        fl2 = QFormLayout(g2)
        
        self.font_preset_dropdown = QComboBox()
        self.btn_browse_font_1 = QPushButton("Install Custom Font...")
        self.btn_browse_font_1.clicked.connect(self._browse_font)
        font1_layout = QHBoxLayout()
        font1_layout.addWidget(self.font_preset_dropdown)
        font1_layout.addWidget(self.btn_browse_font_1)

        self.multi_font_mode = QComboBox()
        self.multi_font_mode.addItems(["Single Primary Font", "Dual Fonts (Alternating)", "Dual Fonts (Random)"])
        self.font_preset_choice_2 = QComboBox()
        font2_layout = QHBoxLayout()
        font2_layout.addWidget(self.font_preset_choice_2)

        self.font_size_slider = self._create_slider(10, 200, 145)
        self.bottom_font_size_slider = self._create_slider(10, 200, 145)
        self.max_words_slider = self._create_slider(1, 8, 2)
        self.max_chars_slider = self._create_slider(15, 60, 28)
        self.lines_mode_dropdown = QComboBox()
        self.lines_mode_dropdown.addItems(["Auto (Wrap if needed)", "Single Line Forced", "Two Lines Forced"])
        self.line_spacing_scale = self._create_double_spinbox(0.5, 1.5, 0.02, 0.82)
        self.vertical_alignment = QComboBox()
        self.vertical_alignment.addItems(["Center", "Bottom", "Top", "Bottom-Third"])
        self.vertical_alignment.setCurrentText("Center")
        
        self.text_animation_style = QComboBox()
        self.text_animation_style.addItems(["Classic Wipe (Default)", "Fade-in Blur", "Slide"])
        self.text_animation_style.setCurrentText("Classic Wipe (Default)")
        
        self.pos_offset_x = self._create_slider(-500, 500, 0)
        self.pos_offset_y = self._create_slider(-500, 500, 0)
        
        fl2.addRow('Font Preset:', self.font_preset_dropdown)
        fl2.addRow('Custom Font 1:', font1_layout)
        fl2.addRow('Multi-Font Mode:', self.multi_font_mode)
        fl2.addRow('Font 2 Preset:', self.font_preset_choice_2)
        fl2.addRow('Custom Font 2:', font2_layout)
        fl2.addRow('Top Font Size:', self.font_size_slider)
        fl2.addRow('Bottom Font Size:', self.bottom_font_size_slider)
        fl2.addRow('Max Words:', self.max_words_slider)
        fl2.addRow('Lines Mode:', self.lines_mode_dropdown)
        fl2.addRow('Line Spacing:', self.line_spacing_scale)
        fl2.addRow('Alignment:', self.vertical_alignment)
        fl2.addRow('Text Animation:', self.text_animation_style)
        fl2.addRow('X Offset:', self.pos_offset_x)
        fl2.addRow('Y Offset:', self.pos_offset_y)
        
        self.random_brush_highlights = QCheckBox("Enable Random Green Brush Highlights")
        fl2.addRow(self.random_brush_highlights)
        
        l1.addWidget(g2)
        l1.addStretch()

        # 3. 3D Plastic & Color
        t2, l2 = self.create_scrollable_tab()
        self.tabs.addTab(t2, '3D & Color')
        g3 = QGroupBox('Sheen & Shadows')
        fl3 = QFormLayout(g3)
        self.show_shadow = QCheckBox("Show Drop Shadow")
        self.show_shadow.setChecked(True)
        self.shadow_depth = self._create_slider(0, 50, 3)
        self.shadow_step_x = self._create_slider(-20, 20, 1)
        self.shadow_step_y = self._create_slider(-20, 20, 1)
        self.sheen_3d_scope = QComboBox()
        self.sheen_3d_scope.addItems([
            "Both Lines (Top + Bottom - Default)", 
            "Top Line Only (Upper Line)", 
            "Bottom Line Only (Lower Line)", 
            "Disabled (Flat 2D Typography)"
        ])
        self.gloss_intensity = self._create_double_spinbox(0.0, 2.5, 0.1, 0.7)
        
        self.t1_top = ColorButton('#FFBD59')
        self.t1_mid = ColorButton('#FF7300')
        self.t1_bot = ColorButton('#E53900')
        self.t1_shadow = ColorButton('#3D1400')
        self.t2_top = ColorButton('#FFFFFF')
        self.t2_mid = ColorButton('#FFFFFF')
        self.t2_bot = ColorButton('#E2E8F0')
        self.t2_shadow = ColorButton('#222225')
        
        self.show_glow = QCheckBox("Enable Glow")
        self.show_glow.setChecked(True)
        self.t1_glow = ColorButton('#FF7300')
        self.t2_glow = ColorButton('#222225')
        self.glow_strength = self._create_double_spinbox(0.1, 5.0, 0.1, 1.0)
        
        self.bg_box_enable = QCheckBox("Enable Solid Background Box")
        self.bg_box_enable.setChecked(False)
        self.bg_box_color = ColorButton('#F5F2DA')
        
        fl3.addRow(self.show_shadow)
        fl3.addRow('Shadow Depth:', self.shadow_depth)
        fl3.addRow('Sheen Scope:', self.sheen_3d_scope)
        fl3.addRow('Gloss Intensity:', self.gloss_intensity)
        fl3.addRow('T1 Top:', self.t1_top)
        fl3.addRow('T1 Mid:', self.t1_mid)
        fl3.addRow('T1 Bot:', self.t1_bot)
        fl3.addRow('T2 Top:', self.t2_top)
        fl3.addRow('T2 Mid:', self.t2_mid)
        fl3.addRow('T2 Bot:', self.t2_bot)
        
        
        
        # Add Glow settings to layout
        fl3.addRow(self.show_glow)
        fl3.addRow('T1 Glow:', self.t1_glow)
        fl3.addRow('T2 Glow:', self.t2_glow)
        fl3.addRow('Glow Strength:', self.glow_strength)

        # Add BG Box settings to layout
        fl3.addRow(self.bg_box_enable)
        fl3.addRow('BG Box Color:', self.bg_box_color)
        
        l2.addWidget(g3)
        l2.addStretch()

        # 4. Rotoscope & Zoom
        t3, l3 = self.create_scrollable_tab()
        self.tabs.addTab(t3, 'AI FX')
        g4 = QGroupBox('AI Face Zoom')
        fl4 = QFormLayout(g4)
        self.enable_auto_zoom = QCheckBox('Enable Auto-Zoom')
        self.zoom_factor = self._create_double_spinbox(1.0, 2.0, 0.05, 1.18)
        self.zoom_frequency = self._create_slider(1, 10, 3)
        self.zoom_transition_style = QComboBox()
        self.zoom_transition_style.addItems(["🌊 Lush S-Curve Cinematic Glide", "⚡ Fast Snappy CapCut Punch"])
        self.face_detector_model = QComboBox()
        self.face_detector_model.addItems(["YuNet Deep Neural Network", "OpenCV Haar Cascade (Fallback CPU)"])
        self.min_cooldown_slider = self._create_double_spinbox(2.0, 20.0, 0.5, 6.0)
        self.zoom_hold_slider = self._create_double_spinbox(1.5, 15.0, 0.5, 4.0)
        
        fl4.addRow(self.enable_auto_zoom)
        fl4.addRow('Zoom Factor:', self.zoom_factor)
        fl4.addRow('Zoom Frequency:', self.zoom_frequency)
        fl4.addRow('Transition Style:', self.zoom_transition_style)
        fl4.addRow('Zoom Cooldown (Wait):', self.min_cooldown_slider)
        fl4.addRow('Zoom Hold (Duration):', self.zoom_hold_slider)
        l3.addWidget(g4)

        g_track = QGroupBox('Dynamic Face Tracking (Auto-Frame)')
        fl_track = QFormLayout(g_track)
        self.enable_dynamic_tracking = QCheckBox('Enable Continuous Face Tracking')
        self.tracking_mode = QComboBox()
        self.tracking_mode.addItems(["Auto-Zoom to Fill Voids (Method B)", "Edge Clamping (Method A)"])
        self.tracking_smoothness = self._create_slider(1, 30, 15)
        
        self.tracking_start_sec = QLineEdit("0.0")
        self.tracking_end_sec = QLineEdit("0.0")
        
        fl_track.addRow(self.enable_dynamic_tracking)
        fl_track.addRow('Tracking Mode:', self.tracking_mode)
        fl_track.addRow('Smoothness (Frames):', self.tracking_smoothness)
        
        tracking_time_layout = QHBoxLayout()
        tracking_time_layout.addWidget(QLabel("Start (s):"))
        tracking_time_layout.addWidget(self.tracking_start_sec)
        tracking_time_layout.addWidget(QLabel("End (s):"))
        tracking_time_layout.addWidget(self.tracking_end_sec)
        fl_track.addRow('Apply Tracking Time:', tracking_time_layout)
        
        l3.addWidget(g_track)
        
        g5 = QGroupBox('Custom Rotoscope Text')
        fl5 = QFormLayout(g5)
        self.rotoscope_enable = QCheckBox('Enable Custom Rotoscope Text')
        self.enable_3d_parallax = QCheckBox('Enable 3D Parallax (Artificial Camera Move)')
        
        self.custom_roto_text = QLineEdit("CUSTOM TEXT")
        self.custom_roto_font = QComboBox()
        # Will be populated by _populate_font_dropdowns
        
        roto_font_upload_layout = QHBoxLayout()
        self.custom_roto_font_file = QLineEdit()
        self.btn_browse_roto_font = QPushButton('Browse...')
        self.btn_browse_roto_font.clicked.connect(lambda: self._browse_roto_font(self.custom_roto_font_file))
        roto_font_upload_layout.addWidget(self.custom_roto_font_file)
        roto_font_upload_layout.addWidget(self.btn_browse_roto_font)

        self.custom_roto_font_size = self._create_slider(10, 300, 150)
        self.custom_roto_color = ColorButton("#FFFFFF")
        
        self.custom_roto_show_glow = QCheckBox('Enable Glow')
        self.custom_roto_glow_color = ColorButton("#FF7300")
        self.custom_roto_glow_strength = self._create_double_spinbox(0.1, 5.0, 0.1, 1.0)
        
        self.custom_roto_pos_x = self._create_slider(-1000, 1000, 0)
        self.custom_roto_pos_y = self._create_slider(-1000, 1000, 0)
        
        self.rotoscope_start_sec = self._create_double_spinbox(0.0, 999.0, 0.1, 0.0)
        self.rotoscope_end_sec = self._create_double_spinbox(0.0, 999.0, 0.1, 5.0)
        
        fl5.addRow(self.rotoscope_enable)
        fl5.addRow(self.enable_3d_parallax)
        fl5.addRow('Text:', self.custom_roto_text)
        fl5.addRow('Font Preset:', self.custom_roto_font)
        fl5.addRow('Upload Font (TTF):', roto_font_upload_layout)
        fl5.addRow('Font Size:', self.custom_roto_font_size)
        fl5.addRow('Color:', self.custom_roto_color)
        fl5.addRow(self.custom_roto_show_glow)
        fl5.addRow('Glow Color:', self.custom_roto_glow_color)
        fl5.addRow('Glow Strength:', self.custom_roto_glow_strength)
        fl5.addRow('Pos X Nudge:', self.custom_roto_pos_x)
        fl5.addRow('Pos Y Nudge:', self.custom_roto_pos_y)
        fl5.addRow('Start Sec:', self.rotoscope_start_sec)
        fl5.addRow('End Sec:', self.rotoscope_end_sec)
        l3.addWidget(g5)
        l3.addStretch()

        # 5. Audio SFX
        t4, l4 = self.create_scrollable_tab()
        self.tabs.addTab(t4, 'Audio SFX')
        g6 = QGroupBox('Sound Effects')
        fl6 = QFormLayout(g6)
        self.enable_sfx = QCheckBox('Enable SFX')
        self.enable_sfx.setChecked(True)
        self.sfx_preset_dropdown = QComboBox()
        self.sfx_preset_dropdown.addItems([
            "Mixkit Modern Technology Select (Default - 0.5s Clean Click)",
            "Motion Design AfterEffects Pop (0.4s Punchy Pop)",
            "UI Caption Accent (Subtle Soft Bubble Pop)"
        ])
        
        sfx_upload_layout = QHBoxLayout()
        self.sfx_upload_file = QLineEdit()
        self.btn_browse_sfx = QPushButton('Browse...')
        self.btn_browse_sfx.clicked.connect(lambda: self._browse_audio(self.sfx_upload_file))
        sfx_upload_layout.addWidget(self.sfx_upload_file)
        sfx_upload_layout.addWidget(self.btn_browse_sfx)
        
        self.sfx_volume_slider = self._create_double_spinbox(0.05, 1.0, 0.05, 0.30)
        self.sfx_trigger_mode = QComboBox()
        self.sfx_trigger_mode.addItems([
            "Every New Caption Chunk (Every 2-4 Words)",
            "Every 2nd Chunk (More Reserved / Occasional)",
            "Every Single Word Pop-Up (High Energy / Fast Paced)"
        ])
        self.sfx_cooldown_slider = self._create_double_spinbox(0.10, 2.0, 0.05, 0.35)
        
        self.enable_3d_icons = QCheckBox('Enable 3D Icon Overlay (IconScout)')
        self.enable_3d_icons.setChecked(True)
        self.custom_3d_trigger_words = QLineEdit('instagram, money, time, secret, youtube, tiktok, cash, like, subscribe, dollar, stop, go, fast, slow, win, fail, idea, brain, rupees, business, clients, chatgpt, food, marketing, family')
        
        fl6 = QFormLayout()
        fl6.addRow(self.enable_sfx)
        fl6.addRow('Preset:', self.sfx_preset_dropdown)
        fl6.addRow('Custom SFX:', sfx_upload_layout)
        fl6.addRow('Volume:', self.sfx_volume_slider)
        fl6.addRow('Trigger:', self.sfx_trigger_mode)
        fl6.addRow('Cooldown (s):', self.sfx_cooldown_slider)
        fl6.addRow(self.enable_3d_icons)
        fl6.addRow('Custom 3D Trigger Words:', self.custom_3d_trigger_words)
        t4.setLayout(fl6)
        l4.addStretch()

        # Removed Kinematics & FX

        # Populate font dropdowns on launch
        self._populate_font_dropdowns()

    def get_config(self):
        # Maps to the 60+ parameters required by render_video_gui
        return {
            "input_video": self.input_video.text(),
            "input_audio": self.input_audio.text(),
            "audio_aspect": self.audio_aspect.currentText(),
            "accuracy_level": self.accuracy_level.currentText(),
            "font_preset_dropdown": self.font_preset_dropdown.currentText(),
            "multi_font_mode": self.multi_font_mode.currentText(),
            "font_preset_choice_2": self.font_preset_choice_2.currentText(),
            "font_size_slider": self.font_size_slider.value(),
            "bottom_font_size_slider": self.bottom_font_size_slider.value(),
            "show_shadow": self.show_shadow.isChecked(),
            "shadow_depth": self.shadow_depth.value(),
            "shadow_step_x": self.shadow_step_x.value(),
            "shadow_step_y": self.shadow_step_y.value(),
            "sheen_3d_scope": self.sheen_3d_scope.currentText(),
            "gloss_intensity": self.gloss_intensity.value(),
            "t1_top": self.t1_top.get_color(),
            "t1_mid": self.t1_mid.get_color(),
            "t1_bot": self.t1_bot.get_color(),
            "t1_shadow": self.t1_shadow.get_color(),
            "t2_top": self.t2_top.get_color(),
            "t2_mid": self.t2_mid.get_color(),
            "t2_bot": self.t2_bot.get_color(),
            "t2_shadow": self.t2_shadow.get_color(),
            "show_glow": self.show_glow.isChecked(),
            "t1_glow": self.t1_glow.get_color(),
            "t2_glow": self.t2_glow.get_color(),
            "glow_strength": self.glow_strength.value(),
            "bg_box_enable": self.bg_box_enable.isChecked(),
            "bg_box_color": self.bg_box_color.get_color(),
            "max_words_slider": self.max_words_slider.value(),
            "max_chars_slider": self.max_chars_slider.value(),
            "lines_mode_dropdown": self.lines_mode_dropdown.currentText(),
            "line_spacing_scale": self.line_spacing_scale.value(),
            "vertical_alignment": self.vertical_alignment.currentText(),
            "text_animation_style": self.text_animation_style.currentText(),
            "pos_offset_x": self.pos_offset_x.value(),
            "pos_offset_y": self.pos_offset_y.value(),
            "random_brush_highlights": self.random_brush_highlights.isChecked(),
            "output_mode_dropdown": self.output_mode_dropdown.currentText(),
            "enable_auto_zoom": self.enable_auto_zoom.isChecked(),
            "zoom_factor": self.zoom_factor.value(),
            "zoom_frequency": self.zoom_frequency.value(),
            "zoom_transition_style": self.zoom_transition_style.currentText(),
            "face_detector_model": self.face_detector_model.currentText(),
            "min_cooldown_slider": self.min_cooldown_slider.value(),
            "zoom_hold_slider": self.zoom_hold_slider.value(),
            "enable_dynamic_tracking": self.enable_dynamic_tracking.isChecked(),
            "tracking_mode": self.tracking_mode.currentText(),
            "tracking_smoothness": self.tracking_smoothness.value(),
            "tracking_start_sec": float(self.tracking_start_sec.text() or "0"),
            "tracking_end_sec": float(self.tracking_end_sec.text() or "0"),
            "enable_sfx": self.enable_sfx.isChecked(),
            "sfx_preset_dropdown": self.sfx_preset_dropdown.currentText(),
            "sfx_upload_file": self.sfx_upload_file.text(),
            "sfx_volume_slider": self.sfx_volume_slider.value(),
            "sfx_trigger_mode": self.sfx_trigger_mode.currentText(),
            "sfx_cooldown_slider": self.sfx_cooldown_slider.value(),
            "enable_3d_icons": self.enable_3d_icons.isChecked(),
            "custom_3d_trigger_words": self.custom_3d_trigger_words.text(),
            "rotoscope_enable": self.rotoscope_enable.isChecked(),
            "enable_3d_parallax": self.enable_3d_parallax.isChecked(),
            "rotoscope_style": "Text Behind Speaker (Standard Full Rotoscope - Default)",
            "rotoscope_outline_width": 3,
            "custom_roto_text": self.custom_roto_text.text(),
            "custom_roto_font": self.custom_roto_font.currentText(),
            "custom_roto_font_file": self.custom_roto_font_file.text(),
            "custom_roto_font_size": self.custom_roto_font_size.value(),
            "custom_roto_color": self.custom_roto_color.get_color(),
            "custom_roto_show_glow": self.custom_roto_show_glow.isChecked(),
            "custom_roto_glow_color": self.custom_roto_glow_color.get_color(),
            "custom_roto_glow_strength": self.custom_roto_glow_strength.value(),
            "custom_roto_pos_x": self.custom_roto_pos_x.value(),
            "custom_roto_pos_y": self.custom_roto_pos_y.value(),
            "rotoscope_start_sec": self.rotoscope_start_sec.value(),
            "rotoscope_end_sec": self.rotoscope_end_sec.value(),
            "rotoscope_downsample": "0.25 (Fastest / Recommended - 60 FPS)",
        }

    def _populate_font_dropdowns(self):
        from ..core.config import config
        fonts = config.get_available_fonts()
        
        curr1 = self.font_preset_dropdown.currentText()
        curr2 = self.font_preset_choice_2.currentText()
        curr_roto = self.custom_roto_font.currentText()
        
        self.font_preset_dropdown.clear()
        self.font_preset_choice_2.clear()
        self.custom_roto_font.clear()
        
        self.font_preset_dropdown.addItems(fonts)
        self.font_preset_choice_2.addItems(fonts)
        self.custom_roto_font.addItems(fonts)
        
        if curr1 in fonts: self.font_preset_dropdown.setCurrentText(curr1)
        if curr2 in fonts: self.font_preset_choice_2.setCurrentText(curr2)
        if curr_roto in fonts: self.custom_roto_font.setCurrentText(curr_roto)
        
        self.fonts_updated.emit()

    def _browse_font(self):
        from PySide6.QtWidgets import QFileDialog
        from ..core.config import config
        import os, shutil
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Font", "", "Font Files (*.ttf *.otf *.woff)")
        if file_name:
            try:
                base = os.path.basename(file_name)
                dest = os.path.join(config.USER_FONTS_DIR, base)
                shutil.copy2(file_name, dest)
                self._populate_font_dropdowns()
                self.font_preset_dropdown.setCurrentText(base)
            except Exception as e:
                print(f"Error copying font: {e}")

    def _browse_roto_font(self, line_edit):
        from PySide6.QtWidgets import QFileDialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Font", "", "Font Files (*.ttf *.otf *.woff)")
        if file_name:
            line_edit.setText(file_name)
            
    def _browse_audio(self, line_edit):
        from PySide6.QtWidgets import QFileDialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Audio", "", "Audio Files (*.mp3 *.wav *.aac)")
        if file_name:
            line_edit.setText(file_name)

    def _browse_audio(self, line_edit):
        from PySide6.QtWidgets import QFileDialog
        file_name, _ = QFileDialog.getOpenFileName(self, "Select Audio", "", "Audio Files (*.mp3 *.wav *.aac)")
        if file_name:
            line_edit.setText(file_name)
