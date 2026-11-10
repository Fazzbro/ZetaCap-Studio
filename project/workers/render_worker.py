import sys
from PySide6.QtCore import QThread, Signal
from project.services.backend_renderer import render_video_gui, generate_style_preview_gui

class StylePreviewWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, kwargs, parent=None):
        super().__init__(parent)
        self.kwargs = kwargs

    def run(self):
        try:
            # Reconstruct the exact list of 37 arguments required by generate_style_preview_gui
            args = [
                self.kwargs.get("input_video"),
                self.kwargs.get("words_table"),
                self.kwargs.get("whisper_words_state"),
                self.kwargs.get("all_words_overrides_state"),
                self.kwargs.get("preview_timestamp", 0.0),
                self.kwargs.get("font_preset_dropdown"),
                self.kwargs.get("font_upload"),
                self.kwargs.get("multi_font_mode"),
                self.kwargs.get("font_preset_choice_2"),
                self.kwargs.get("font_file_2"),
                self.kwargs.get("font_size_slider"),
            self.kwargs.get("bottom_font_size_slider"),
                self.kwargs.get("show_shadow"),
                self.kwargs.get("shadow_depth"),
                self.kwargs.get("shadow_step_x"),
                self.kwargs.get("shadow_step_y"),
                self.kwargs.get("sheen_3d_scope"),
                self.kwargs.get("gloss_intensity"),
                self.kwargs.get("t1_top"),
                self.kwargs.get("t1_mid"),
                self.kwargs.get("t1_bot"),
                self.kwargs.get("t1_shadow"),
                self.kwargs.get("t2_top"),
                self.kwargs.get("t2_mid"),
                self.kwargs.get("t2_bot"),
                self.kwargs.get("t2_shadow"),
                self.kwargs.get("show_glow"),
                self.kwargs.get("t1_glow"),
                self.kwargs.get("t2_glow"),
                self.kwargs.get("glow_strength"),
                self.kwargs.get("bg_box_enable"),
                self.kwargs.get("bg_box_color"),
                self.kwargs.get("max_words_slider"),
                self.kwargs.get("max_chars_slider"),
                self.kwargs.get("lines_mode_dropdown"),
                self.kwargs.get("line_spacing_scale"),
                self.kwargs.get("vertical_alignment"),
                self.kwargs.get("pos_offset_x"),
                self.kwargs.get("pos_offset_y"),
                self.kwargs.get("random_brush_highlights"),
                self.kwargs.get("rotoscope_enable"),
                self.kwargs.get("rotoscope_style"),
                self.kwargs.get("rotoscope_outline_width"),
                self.kwargs.get("custom_roto_text"),
                self.kwargs.get("custom_roto_font"),
                self.kwargs.get("custom_roto_font_file"),
                self.kwargs.get("custom_roto_font_size"),
                self.kwargs.get("custom_roto_color"),
                self.kwargs.get("custom_roto_show_glow"),
                self.kwargs.get("custom_roto_glow_color"),
                self.kwargs.get("custom_roto_glow_strength"),
                self.kwargs.get("custom_roto_pos_x"),
                self.kwargs.get("custom_roto_pos_y"),
                self.kwargs.get("rotoscope_start_sec"),
                self.kwargs.get("rotoscope_end_sec"),
                self.kwargs.get("rotoscope_downsample")
            ]
            image_path = generate_style_preview_gui(
                *args,
                multi_preset_mode=self.kwargs.get("multi_preset_mode", "Single Preset (Disabled)"),
                multi_preset_pool=self.kwargs.get("multi_preset_pool", []),
                multi_preset_lock_alignment=self.kwargs.get("multi_preset_lock_alignment", True),
                multi_preset_unified_zoom=self.kwargs.get("multi_preset_unified_zoom", True),
                multi_preset_scale_font_size=self.kwargs.get("multi_preset_scale_font_size", 1.0)
            )
            self.finished.emit(image_path)
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())

class RenderWorker(QThread):
    progress = Signal(float, str)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, kwargs, parent=None):
        super().__init__(parent)
        self.kwargs = kwargs

    def run(self):
        try:
            from project.services.backend_renderer import render_video_gui
            input_video_str = self.kwargs.get("input_video", "")
            if input_video_str and ";" in input_video_str:
                videos = [v.strip() for v in input_video_str.split(";") if v.strip()]
            else:
                videos = [input_video_str] if input_video_str else [None]

            is_batch = len(videos) > 1
            output_paths = []

            for idx, vid_path in enumerate(videos):
                if is_batch:
                    self.progress.emit(0.0, f"Starting final render for video {idx+1}/{len(videos)}...")
                else:
                    self.progress.emit(0.0, "Starting final render...")
                
                # In batch mode, ignore edited words table to force auto-transcription per video
                words_tbl = None if is_batch else self.kwargs.get("words_table")
                whisper_state = None if is_batch else self.kwargs.get("whisper_words_state")
                overrides_state = None if is_batch else self.kwargs.get("all_words_overrides_state")

                args = [
                    vid_path,
                    self.kwargs.get("input_audio"),
                    self.kwargs.get("audio_aspect", "16:9 (YouTube)"),
                    words_tbl,
                    whisper_state,
                    overrides_state,
                    self.kwargs.get("font_preset_dropdown"),
                    self.kwargs.get("font_upload"),
                    self.kwargs.get("multi_font_mode"),
                    self.kwargs.get("font_preset_choice_2"),
                    self.kwargs.get("font_file_2"),
                    self.kwargs.get("font_size_slider"),
                    self.kwargs.get("bottom_font_size_slider"),
                    self.kwargs.get("show_shadow"),
                    self.kwargs.get("shadow_depth"),
                    self.kwargs.get("shadow_step_x"),
                    self.kwargs.get("shadow_step_y"),
                    self.kwargs.get("sheen_3d_scope"),
                    self.kwargs.get("gloss_intensity"),
                    self.kwargs.get("t1_top"),
                    self.kwargs.get("t1_mid"),
                    self.kwargs.get("t1_bot"),
                    self.kwargs.get("t1_shadow"),
                    self.kwargs.get("t2_top"),
                    self.kwargs.get("t2_mid"),
                    self.kwargs.get("t2_bot"),
                    self.kwargs.get("t2_shadow"),
                    self.kwargs.get("show_glow"),
                    self.kwargs.get("t1_glow"),
                    self.kwargs.get("t2_glow"),
                    self.kwargs.get("glow_strength"),
                    self.kwargs.get("bg_box_enable"),
                    self.kwargs.get("bg_box_color"),
                    self.kwargs.get("max_words_slider"),
                    self.kwargs.get("max_chars_slider"),
                    self.kwargs.get("lines_mode_dropdown"),
                    self.kwargs.get("line_spacing_scale"),
                    self.kwargs.get("vertical_alignment"),
                    self.kwargs.get("pos_offset_x"),
                    self.kwargs.get("pos_offset_y"),
                    self.kwargs.get("random_brush_highlights"),
                    self.kwargs.get("output_mode_dropdown"),
                    self.kwargs.get("enable_auto_zoom"),
                    self.kwargs.get("zoom_factor"),
                    self.kwargs.get("zoom_frequency"),
                    self.kwargs.get("zoom_transition_style"),
                    self.kwargs.get("face_detector_model"),
                    self.kwargs.get("min_cooldown_slider"),
                    self.kwargs.get("zoom_hold_slider"),
                    self.kwargs.get("enable_dynamic_tracking", False),
                    self.kwargs.get("tracking_mode", "Auto-Zoom to Fill Voids (Method B)"),
                    self.kwargs.get("tracking_smoothness", 15),
                    self.kwargs.get("tracking_start_sec", 0.0),
                    self.kwargs.get("tracking_end_sec", 0.0),
                    self.kwargs.get("enable_sfx"),
                    self.kwargs.get("sfx_preset_dropdown"),
                    self.kwargs.get("sfx_upload_file"),
                    self.kwargs.get("sfx_volume_slider"),
                    self.kwargs.get("sfx_trigger_mode"),
                    self.kwargs.get("sfx_cooldown_slider"),
                    self.kwargs.get("rotoscope_enable"),
                    self.kwargs.get("rotoscope_style"),
                    self.kwargs.get("rotoscope_outline_width"),
                    self.kwargs.get("custom_roto_text"),
                    self.kwargs.get("custom_roto_font"),
                    self.kwargs.get("custom_roto_font_file"),
                    self.kwargs.get("custom_roto_font_size"),
                    self.kwargs.get("custom_roto_color"),
                    self.kwargs.get("custom_roto_show_glow"),
                    self.kwargs.get("custom_roto_glow_color"),
                    self.kwargs.get("custom_roto_glow_strength"),
                    self.kwargs.get("custom_roto_pos_x"),
                    self.kwargs.get("custom_roto_pos_y"),
                    self.kwargs.get("rotoscope_start_sec"),
                    self.kwargs.get("rotoscope_end_sec"),
                    self.kwargs.get("rotoscope_downsample"),
                    self.kwargs.get("text_animation_style", "Classic Wipe (Default)"),
                    "tiny" if "Fast" in str(self.kwargs.get("accuracy_level", "Fast")) else "small",
                    self.kwargs.get("enable_3d_parallax", False),
                    self.kwargs.get("color_grade_style", "None"),
                    self.kwargs.get("custom_lut_path", ""),
                    self.progress.emit
                ]
                output_path = render_video_gui(
                    *args,
                    multi_preset_mode=self.kwargs.get("multi_preset_mode", "Single Preset (Disabled)"),
                    multi_preset_pool=self.kwargs.get("multi_preset_pool", []),
                    multi_preset_lock_alignment=self.kwargs.get("multi_preset_lock_alignment", True),
                    multi_preset_unified_zoom=self.kwargs.get("multi_preset_unified_zoom", True),
                    multi_preset_scale_font_size=self.kwargs.get("multi_preset_scale_font_size", 1.0)
                )
                output_paths.append(output_path)
            
            if is_batch:
                self.finished.emit(f"Batch render complete! {len(output_paths)} files saved to output/ directory.")
            else:
                self.finished.emit(output_paths[0])
        except Exception as e:
            import traceback
            self.error.emit(traceback.format_exc())
