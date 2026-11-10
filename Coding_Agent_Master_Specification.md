# Comprehensive Coding Agent Specification

This document is a master instruction set for converting my existing
Python + Gradio application into a production-grade Windows desktop
application.

## Mission

Transform the existing application into a native PySide6 desktop
application without removing any features.

## Core Principles

-   Preserve all functionality.
-   Refactor, don't rewrite algorithms unnecessarily.
-   Modular architecture.
-   Production quality only.
-   No placeholder code.
-   Maintain backward compatibility where practical.

## Required Architecture

    project/
      app.py
      core/
      ui/
      workers/
      services/
      assets/
      config/
      output/
      tests/
      docs/

## UI Requirements

-   PySide6
-   Dark theme
-   Dockable panels
-   Timeline
-   Video preview
-   Caption editor
-   Export dialog
-   Settings dialog
-   Keyboard shortcuts
-   Responsive layouts

## Backend Requirements

-   Separate UI and business logic
-   QThread/QRunnable for long tasks
-   Logging
-   Config management
-   Dependency injection where useful
-   Type hints
-   Dataclasses
-   Unit tests

## Preserve Existing Features

-   Whisper transcription
-   Caption rendering
-   Font management
-   Animation engine
-   Face detection
-   Auto zoom
-   Rotoscoping
-   Video export
-   Preview rendering
-   Word editor
-   Search and pagination

## Packaging

-   PyInstaller
-   Installer
-   Version info
-   App icon
-   requirements.txt
-   pyproject.toml

## Acceptance Criteria

The final application should feel comparable to modern desktop editors
and be suitable for commercial release.

Continue implementation in small milestones: 1. Audit 2. Modularize 3.
Replace Gradio with PySide6 4. Integrate backend 5. Optimize 6. Test 7.
Package 8. Release
