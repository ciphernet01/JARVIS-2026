# Phase 7: Computer Vision

Phase 7 introduces computer vision capabilities to JARVIS.

## Delivered
- Vision engine for webcam capture
- Face detection using OpenCV Haar cascades
- Snapshot capture with automatic annotation
- Optional file-based image analysis
- Camera skill integrated into the skill registry

## Main files
- modules/vision/camera.py
- modules/vision/__init__.py
- modules/skills/integration_skills.py
- modules/skills/factory.py

## Behavior
- Commands like "open camera", "camera", "detect faces", and "face detect" are now routed to the vision engine.
- Captured snapshots are saved into a captures folder.
- The skill reports how many faces were detected.

## Next step
Phase 8: Performance Optimization
