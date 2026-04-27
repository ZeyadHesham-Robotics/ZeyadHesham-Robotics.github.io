# Multi-Object Detection Plan

## Architecture: Strategy Pattern with Per-Mode HSV Presets

### Step 1 — Create base detector + detector registry

Add a `BaseDetector` abstract class and a `DetectorRegistry` that holds named detectors:

```
BaseDetector (abstract)
  ├── detect_with_mask(frame) → (DetectionResult | None, mask)
  ├── uses_hsv() → bool          # True if HSV tuner applies
  └── get_default_color_config() → ColorConfig | None
```

### Step 2 — Refactor CubeDetector into HSVShapeDetector

Rename/generalize `CubeDetector` to `HSVShapeDetector` with configurable shape parameters:
- `min_aspect` — low for screwdrivers (elongated), higher for cubes
- `max_aspect` — cap for screwdrivers (reject square shapes)
- `min_solidity` — same as now
- Each instance gets its own `ColorConfig` preset

Presets:
- **Orange Cube**: H 5-38, S 80-255, V 80-255, aspect 0.30-1.0
- **Black Cube**: H 0-179, S 0-60, V 0-50, aspect 0.30-1.0
- **Screwdriver**: H/S/V TBD by user tuning, aspect 0.05-0.35 (elongated)

### Step 3 — Create ArUcoDetector

New detector class using `cv2.aruco`:
- Dictionary: `DICT_6X6_250`
- Detects markers, extracts center + angle from corners
- Returns `DetectionResult` with center, angle, bounding box
- `uses_hsv()` returns `False` — no HSV tuner needed
- Mask output: drawn marker outlines on black background

### Step 4 — Add dropdown to GUI

Add a `ttk.Combobox` dropdown in the top row (above the panels) or in the Connection panel:
- Options: "Orange Cube", "Black Cube", "Screwdriver", "ArUco Tag"
- On selection change → swap active detector in GUIPipeline
- If new detector uses HSV → load its ColorConfig into HSV sliders
- If ArUco → disable/grey out HSV sliders

### Step 5 — Wire detector switching in GUIPipeline

- `GUIPipeline` holds a `DetectorRegistry` with all detectors pre-registered
- `_on_detector_change(name)` callback:
  1. Set `self.detector = registry.get(name)`
  2. If HSV-based: update `self.color_cfg` reference + refresh sliders
  3. Reset tracker + stability guard
- HSV "Save" button saves to per-mode file (e.g., `color_orange_cube.json`)

### Step 6 — Update HSV tuner to work with active detector

- When switching to HSV-based detector: enable sliders, load that detector's ColorConfig
- When switching to ArUco: disable sliders, show "N/A" label
- Slider changes update the ACTIVE detector's ColorConfig only

## Files Modified
- `KUKA_Cube_CV_V4.py` — all changes in this single file (new classes + GUI + pipeline wiring)

## No Breaking Changes
- DetectionResult stays the same
- CoordinateTransformer, StabilityGuard, OverlayRenderer unchanged
- All existing features (jog, follow, capture/confirm, pick-and-place) work with any detector
