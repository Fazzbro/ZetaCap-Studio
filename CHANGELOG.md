# Changelog

All notable changes to the Iman Gadzhi Style Captions Studio Pro project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.11.0] - 2026-07-21
### Added
- **2-Line Vertical Distance Scale Slider (`line_spacing_scale` in `tiny_modified.py`):** Added `2-Line Vertical Distance Scale` slider (`0.50` to `1.50`, default `0.82`) in **Tab 1: Media & Typography** right next to the lines mode selector.
  - **Maximum Closeness Without Touching:** Set default leading (`0.82`) to achieve maximum closeness (~5px separation) between top and bottom lines of 2-line stacked captions without touching or colliding.
  - **Synchronized Preview & Render Engines:** Plumbed `line_spacing_scale` through both `generate_style_preview_gui` (`render_stacked_captions_png`) and `render_video_gui` (`base_y_t1` / `base_y_t2`), guaranteeing that the live preview exactly matches the exported video.
  - **Full Preset Serialization:** Integrated `line_spacing_scale` into `save_studio_preset_gui` and `load_studio_preset_gui` (`preset_inputs_list`), ensuring line spacing preferences are saved inside `.json` studio presets.

## [2.10.0] - 2026-07-21
### Added
- **Phase 8 (Live Instant Preview with Real Video First Frame Background in `tiny_modified.py`):** Upgraded `generate_style_preview_gui` to extract and use the exact first frame (`t=0`) of the uploaded source video as the preview background.
  - **Dynamic Frame Extraction:** Automatically opens the uploaded video using `VideoFileClip.get_frame(0)` and sets the preview canvas resolution to match the actual video dimensions (`1080x1920`, `720x1280`, `1920x1080`, etc.).
  - **Instant Reactive UI Wiring:** Wired `input_video` directly into `preview_inputs` so uploading or changing a video immediately regenerates the live style preview image with your real video background and exact typography coordinates.
  - **Graceful Fallback:** Maintains clean `(1080, 1920)` dark slate background when no video is uploaded (`video_file=None`).

## [2.9.0] - 2026-07-21
### Added
- **Phase 7 (Typography Font Selector Dropdown in `tiny_modified.py`):** Added dedicated `Typography Font Preset` dropdown right above the custom font upload box in **Tab 1: Media & Typography**.
  - **Pre-Loaded Options:** Instantly choose from `Poppins Bold (Default)`, `Helvetica Bold` (`Helvetica-Bold.ttf`), `Helvetica Oblique` (`Helvetica-Oblique.ttf`), `SF Pro Display Medium` (`SFPRODISPLAYMEDIUM.OTF`), `Fraunces` (`Fraunces_72pt_Soft-BoldItalic.ttf`), or `Poppins Medium` (`Poppins-Medium.ttf`), right alongside the fallback `Custom Uploaded (Use File Below)`.
  - **Unified Font Resolution Engine (`get_resolved_font_path`):** Built a universal font path resolver that ensures both PIL (`ImageFont.truetype`) 3D plastic extruded rendering and MoviePy text clips receive exact, absolute `.ttf/.otf` paths without fallback degradation.
  - **Complete Preset Serialization:** `font_preset` choice is saved directly into every exported `.json` studio preset and restored automatically when loaded (`save_studio_preset_gui` / `load_studio_preset_gui`).

## [2.8.0] - 2026-07-20
### Added
- **Phase 6 (Studio Preset Management & Configuration Memory in `tiny_modified.py`):** Added dedicated `💾 6. Save & Load Studio Presets` tab allowing editors to save and restore all 28 studio settings (typography scales, color gradients, 3D extrusion shadows, positioning offsets, and AI camera tracking/cadence parameters) to/from reusable `.json` preset files.
  - **Export Preset:** Click `💾 EXPORT PRESET TO FILE (.json)` to generate and download your custom configuration file.
  - **Instant Restore:** Upload or select any `.json` preset file using `📂 Upload / Select Preset (.json) File` or click `🚀 APPLY PRESET SETTINGS TO STUDIO` to instantly update all sliders, dropdowns, and color pickers across the entire studio interface.
- **Phase 5 (Dynamic Face Tracking & Occasional Auto-Zoom Engine in `tiny_modified.py`):** Created a dedicated, standalone copy `tiny_modified.py` per the Core Directive (leaving `tiny.py` completely unmodified). Added **`📸 5. Face Tracking & Occasional Auto-Zoom`** tab allowing editors to enable automatic AI camera tracking during `🎬 Burn directly onto Source Video (.MP4)` rendering.
  - **D Drive Model Cache:** Configured both OpenCV face detection models and Whisper transcription models (`tiny.pt`) to download and cache strictly inside `D:\ai_models\opencv` and `D:\ai_models\whisper` per user specification.
  - **Dual Face Detection Models:** Integrated OpenCV YuNet deep learning neural network (`face_detection_yunet_2023mar.onnx`, ~232 KB) as primary detector for fast, robust tracking (under 100ms for entire video), with OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`, ~930 KB) as automatic CPU fallback.
  - **Intelligent Cadence & Keyword Triggering:** Replaced intensive/erratic block-counting with **`🧠 Intelligent Cadence (Stay Wide 6s ➔ Hold Zoom 4s - RECOMMENDED)`** and **`🔀 Keyword & Emphasis Trigger (Zoom on ! / ? / High Impact Words)`**. Includes interactive sliders for `⏳ Cooldown Interval Between Zooms (2.0s - 20.0s)` and `⏱️ Zoom Hold Duration (1.5s - 15.0s)` for calm, studio-grade pacing.
  - **Rock-Steady Camera Anchor Lock (`locked_face_cx/cy`):** Added a pre-processing center-locking pass across every continuous zoom-in hold period. By calculating the average anchor coordinates across all chunks within a zoom hold, the camera never shifts, jitters, or drifts sideways/upwards during the 4-second close-up.
  - **Lush S-Curve Cinematic Transitions:** Replaced rigid linear/cubic easing with pre-calculated **Quintic Smootherstep S-Curve (`0.60s Ease-In-Out`)** transitions. Camera glides from absolute rest right to the target anchor and cushions to a gentle stop when punching in or zooming out. Choices include `🌊 Lush S-Curve Cinematic Glide (0.60s Ease-In-Out - RECOMMENDED)`, `🎞️ Standard Cinematic Pan & Zoom (0.35s Cosine Ease)`, and `⚡ Fast Snappy CapCut Punch (0.20s Cubic Ease)`.
### Changed
- **Typography Font Scale Range:** Expanded `font_size_slider` in `tiny_modified.py` from `80-200 px` down to **`50-200 px`** (with a finer `2 px` step) so captions can be made truly compact for smaller screens or denser text blocks.
- **Phase 4 (Interactive Word Editor Table without Timestamps):** Added dedicated `✍️ 2. Interactive Word Editor` tab with `🎧 STEP 1: TRANSCRIBE & EXTRACT WORDS TABLE`. Displays only `["ID", "Word Text"]` inside an editable table (`gr.Dataframe`) while preserving original Whisper start/end timestamps behind the scenes (`whisper_words_state`). Users can fix spelling, capitalize proper nouns, or add emojis before video rendering (`render_video_gui`).
- **Phase 1 (Custom Chunk & Line Splitting Rules):** Added `max_words_per_chunk` (defaulted to 2), `max_chars_per_line` (defaulted to 28), and `lines_per_caption` splitting rules for fine-grained typography control.
- **Phase 2 (Text Caption Positioning & Live Instant Previews):** Added `vertical_alignment` presets (`Lower Third`, `Center`, `Upper Third`, `Bottom Edge`), `pos_offset_x` / `pos_offset_y` fine nudges (-500px to +500px), and instant `.change` + `app.load` live style preview binding.
- **Phase 3 (Direct Video Overlay Mode):** Added `output_mode_dropdown` supporting `🟢 Chroma Key Green Screen (.MP4)` and `🎬 Burn directly onto Source Video (.MP4)`.
- **System Stability & Warning Filters:** Suppressed noisy third-party Starlette/Gradio deprecation warnings (`StarletteDeprecationWarning`), ensured UTF-8 console output for Windows terminals (`sys.stdout.reconfigure`), added `is not` MoviePy clip identity checks, and ensured all media/audio clip handles are cleanly closed after export.
### Removed
- Removed transparent alpha exporting options (`.MOV`/`.WEBM`) per user request to keep local rendering streamlined and fast.
- Cleaned up all temporary render outputs, test scratch clips, and `__pycache__` directories.

## [2.7.0] - 2026-07-19
### Changed
- Consolidated local studio application into a single unified script (`tiny.py` updated to `v2.7 PRO LOCAL`), eliminating code duplication across `tiny_local_studio.py` per explicit user option selection.
- Updated `README.md` launch instructions to point directly to `python tiny.py`.
### Removed
- Removed `tiny_local_studio.py` (`git rm`) now that `tiny.py` serves cleanly as the standalone local studio without cloud dependencies.

## [2.6.0] - 2026-07-19
### Added
- `.gitignore` file covering virtual environments, `__pycache__`, environment secrets (`.env`), and temporary/rendered media files (`*.mp4`, `*.mov`, `gui_output_captions.mp4`, `live_style_preview.png`).
- `tiny_local_studio.py` standalone local studio execution script (created pursuant to our Core Directive on File Preservation During Major Modifications) optimized for pure local execution without external cloud or Hugging Face Spaces hooks.
### Changed
- Updated `README.md` to remove Hugging Face Spaces YAML metadata headers (`sdk: gradio`, `app_file`, etc.), Hugging Face Spaces live badges, and cloud deployment descriptions.
- Updated launch documentation to guide users directly to running `python tiny_local_studio.py` locally while preserving `tiny.py` as an untouched fallback.
### Removed
- Removed `huggingface_hub<0.26.0` dependency requirement from `requirements.txt`.
- Removed `demo = app` Hugging Face Spaces global entrypoint assignment in `tiny_local_studio.py`.
- Gently removed the `deploy_dist/` Hugging Face cloud deployment distribution directory.
