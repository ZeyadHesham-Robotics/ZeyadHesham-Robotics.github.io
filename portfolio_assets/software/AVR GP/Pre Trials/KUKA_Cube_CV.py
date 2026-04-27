"""
kuka_vision.py
==============
OOP-refactored vision pipeline for orange cube detection → KUKA robot.

Classes
-------
CameraConfig      – camera parameters & intrinsics
RobotConfig       – robot transform & workspace limits
ColorConfig       – HSV segmentation parameters
DetectionResult   – dataclass for a single detection
KalmanTracker     – 2-D position smoother
CubeDetector      – frame-level detection logic
CoordinateTransformer – camera → robot coordinate math
StabilityGuard    – emit a pose only after N stable frames
RobotBridge       – TCP sender (disabled by default)
VisionPipeline    – top-level run loop + overlay rendering
"""

import cv2
import numpy as np
import socket
import json
import time
import csv
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from EkiManager import EkiManager
from JointPosition import JointPosition


# ══════════════════════════════════════════════════════════════════
#  CONFIG DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class CameraConfig:
    index: int          = 1
    width: int          = 640
    height: int         = 480
    fx: float           = 800.0          # ← replace with calibrated value
    fy: float           = 800.0
    cx: Optional[float] = None           # principal point X (defaults to width/2)
    cy: Optional[float] = None           # principal point Y (defaults to height/2)
    backend: int        = cv2.CAP_MSMF
    auto_detect: bool   = True

    def principal_point(self):
        return (
            self.cx if self.cx is not None else self.width  / 2.0,
            self.cy if self.cy is not None else self.height / 2.0,
        )

    @classmethod
    def from_json(cls, path: str) -> "CameraConfig":
        with open(path) as f:
            return cls(**json.load(f))

    def to_json(self, path: str):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)


@dataclass
class RobotConfig:
    cam_offset_x: float     =  600.0   # mm – measure precisely!
    cam_offset_y: float     =    0.0
    cam_offset_z: float     =  800.0
    robot_a: float          =  180.0
    robot_b: float          =    0.0
    workspace_x: tuple      = (300.0, 900.0)
    workspace_y: tuple      = (-400.0, 400.0)
    tcp_ip: str             = "192.168.1.1"
    tcp_port: int           = 54610
    homePos = JointPosition([0, -90, 90, 0, 90, -90], [0]*6)


    ekiManager = EkiManager()
    ekiManager.connect(tcp_ip,tcp_port)  # Connect to robot
    @classmethod
    def from_json(cls, path: str) -> "RobotConfig":
        with open(path) as f:
            data = json.load(f)
            data["workspace_x"] = tuple(data["workspace_x"])
            data["workspace_y"] = tuple(data["workspace_y"])
            return cls(**data)


@dataclass
class ColorConfig:
    lower_h: int  =   8
    lower_s: int  = 100
    lower_v: int  = 100
    upper_h: int  =  35
    upper_s: int  = 255
    upper_v: int  = 255
    min_area: int = 1500
    kernel_size: int = 7

    def lower(self) -> np.ndarray:
        return np.array([self.lower_h, self.lower_s, self.lower_v])

    def upper(self) -> np.ndarray:
        return np.array([self.upper_h, self.upper_s, self.upper_v])

    @classmethod
    def from_json(cls, path: str) -> "ColorConfig":
        with open(path) as f:
            return cls(**json.load(f))

    def to_json(self, path: str):
        with open(path, "w") as f:
            json.dump(asdict(self), f, indent=2)


# ══════════════════════════════════════════════════════════════════
#  DETECTION RESULT
# ══════════════════════════════════════════════════════════════════

@dataclass
class DetectionResult:
    cx_px: float          # contour center X (pixels)
    cy_px: float          # contour center Y (pixels)
    angle_deg: float      # in-plane rotation [0, 90)
    pixel_size: float     # max(width, height) of bounding rect
    area: float
    box: np.ndarray       # 4×2 rotated rect corners
    # Filled in by CoordinateTransformer
    x_cam_mm: float = 0.0
    y_cam_mm: float = 0.0
    z_cam_mm: float = 0.0
    x_robot_mm: float = 0.0
    y_robot_mm: float = 0.0
    z_robot_mm: float = 0.0
    in_workspace: bool = False
    timestamp: float = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════
#  KALMAN TRACKER  (2-D image-plane smoothing)
# ══════════════════════════════════════════════════════════════════

class KalmanTracker:
    """
    Simple constant-velocity Kalman filter on (cx, cy) in pixel space.
    Call update() with each new measurement; get smoothed estimate back.
    """

    def __init__(self, process_noise: float = 1e-2, measure_noise: float = 1e1):
        self.kf = cv2.KalmanFilter(4, 2)   # state: [x, y, vx, vy]

        dt = 1.0
        self.kf.transitionMatrix = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1,  0],
            [0, 0, 0,  1],
        ], dtype=np.float32)

        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ], dtype=np.float32)

        self.kf.processNoiseCov     = np.eye(4, dtype=np.float32) * process_noise
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * measure_noise
        self.kf.errorCovPost        = np.eye(4, dtype=np.float32)

        self._initialized = False

    def update(self, cx: float, cy: float) -> tuple[float, float]:
        measurement = np.array([[np.float32(cx)], [np.float32(cy)]])

        if not self._initialized:
            self.kf.statePre = np.array(
                [[cx], [cy], [0.0], [0.0]], dtype=np.float32
            )
            self._initialized = True

        self.kf.predict()
        corrected = self.kf.correct(measurement)
        return float(corrected[0]), float(corrected[1])

    def reset(self):
        self._initialized = False


# ══════════════════════════════════════════════════════════════════
#  CUBE DETECTOR
# ══════════════════════════════════════════════════════════════════

class CubeDetector:
    """
    Detects the largest orange blob in a BGR frame and returns
    a DetectionResult (pixel-space only; no robot coords yet).
    """

    def __init__(self, color_cfg: ColorConfig):
        self.color_cfg = color_cfg
        self.kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (color_cfg.kernel_size, color_cfg.kernel_size),
        )

    def build_mask(self, frame: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        hsv     = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        mask    = cv2.inRange(hsv, self.color_cfg.lower(), self.color_cfg.upper())
        mask    = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self.kernel, iterations=1)
        mask    = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel, iterations=2)
        return mask

    def detect(self, frame: np.ndarray) -> Optional[DetectionResult]:
        mask = self.build_mask(frame)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None

        c    = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < self.color_cfg.min_area:
            return None

        rect              = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), angle = rect

        # Normalise angle so the long axis is always the reference
        if rw < rh:
            angle += 90
        angle = angle % 90   # collapse 90° cube symmetry → [0, 90)

        box        = np.intp(cv2.boxPoints(rect))
        pixel_size = max(rw, rh)

        return DetectionResult(
            cx_px      = cx,
            cy_px      = cy,
            angle_deg  = angle,
            pixel_size = pixel_size,
            area       = area,
            box        = box,
        )

    def detect_with_mask(
        self, frame: np.ndarray
    ) -> tuple[Optional[DetectionResult], np.ndarray]:
        mask   = self.build_mask(frame)
        result = self._detect_from_mask(frame, mask)
        return result, mask

    # ── internal helper so detect() and detect_with_mask() share logic ──
    def _detect_from_mask(
        self, frame: np.ndarray, mask: np.ndarray
    ) -> Optional[DetectionResult]:
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None

        c    = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < self.color_cfg.min_area:
            return None

        rect              = cv2.minAreaRect(c)
        (cx, cy), (rw, rh), angle = rect

        if rw < rh:
            angle += 90
        angle = angle % 90

        box        = np.intp(cv2.boxPoints(rect))
        pixel_size = max(rw, rh)

        return DetectionResult(
            cx_px      = cx,
            cy_px      = cy,
            angle_deg  = angle,
            pixel_size = pixel_size,
            area       = area,
            box        = box,
        )


# ══════════════════════════════════════════════════════════════════
#  COORDINATE TRANSFORMER
# ══════════════════════════════════════════════════════════════════

class CoordinateTransformer:
    """
    Camera-pixel  →  camera-3D  →  robot-base conversion.
    Mutates the DetectionResult in-place and returns it.
    """

    def __init__(
        self,
        cam_cfg:    CameraConfig,
        robot_cfg:  RobotConfig,
        cube_size_m: float = 0.05,
    ):
        self.cam_cfg     = cam_cfg
        self.robot_cfg   = robot_cfg
        self.cube_size_m = cube_size_m
        self.cx0, self.cy0 = cam_cfg.principal_point()

    def transform(self, result: DetectionResult) -> Optional[DetectionResult]:
        """
        Returns the same result object enriched with robot coords,
        or None if pixel_size is degenerate.
        """
        if result.pixel_size <= 1:
            return None

        # ── depth from apparent size (pinhole model) ──
        Z = (self.cam_cfg.fx * self.cube_size_m) / result.pixel_size  # metres
        X = ((result.cx_px - self.cx0) * Z) / self.cam_cfg.fx
        Y = ((result.cy_px - self.cy0) * Z) / self.cam_cfg.fy

        # metres → mm
        result.x_cam_mm = X * 1000.0
        result.y_cam_mm = Y * 1000.0
        result.z_cam_mm = Z * 1000.0

        # ── rigid transform to robot base frame ──
        result.x_robot_mm = self.robot_cfg.cam_offset_x + result.x_cam_mm
        result.y_robot_mm = self.robot_cfg.cam_offset_y - result.y_cam_mm
        result.z_robot_mm = self.robot_cfg.cam_offset_z - result.z_cam_mm

        # ── workspace check ──
        wx_lo, wx_hi = self.robot_cfg.workspace_x
        wy_lo, wy_hi = self.robot_cfg.workspace_y
        result.in_workspace = (
            wx_lo < result.x_robot_mm < wx_hi
            and wy_lo < result.y_robot_mm < wy_hi
        )

        return result

    def to_e6pos(self, result: DetectionResult) -> str:
        return (
            f"{{X {result.x_robot_mm:.2f}, "
            f"Y {result.y_robot_mm:.2f}, "
            f"Z {result.z_robot_mm:.2f}, "
            f"A {self.robot_cfg.robot_a:.2f}, "
            f"B {self.robot_cfg.robot_b:.2f}, "
            f"C {result.angle_deg:.2f}}}"
        )


# ══════════════════════════════════════════════════════════════════
#  STABILITY GUARD
# ══════════════════════════════════════════════════════════════════

class StabilityGuard:
    """
    Only passes a DetectionResult downstream after the robot-space
    position has been stable for `required_frames` consecutive frames
    within `threshold_mm` mm.
    """

    def __init__(self, required_frames: int = 5, threshold_mm: float = 5.0):
        self.required_frames = required_frames
        self.threshold_mm    = threshold_mm
        self._history: list[tuple[float, float, float]] = []
        self._stable_count   = 0

    def is_stable(self, result: DetectionResult) -> bool:
        pos = (result.x_robot_mm, result.y_robot_mm, result.z_robot_mm)

        if not self._history:
            self._history.append(pos)
            self._stable_count = 1
            return False

        last = self._history[-1]
        dist = np.linalg.norm(np.array(pos) - np.array(last))

        if dist < self.threshold_mm:
            self._stable_count += 1
        else:
            self._stable_count = 1

        self._history = [pos]   # only keep last

        return self._stable_count >= self.required_frames

    def reset(self):
        self._history      = []
        self._stable_count = 0


# ══════════════════════════════════════════════════════════════════
#  ROBOT BRIDGE  (TCP sender)
# ══════════════════════════════════════════════════════════════════

class RobotBridge:
    """
    Sends E6POS strings to a KUKA controller over TCP.
    Set enabled=False for dry-run / simulation mode.
    """

    def __init__(self, ip: str, port: int, enabled: bool = False):
        self.ip      = ip
        self.port    = port
        self.enabled = enabled

    def send(self, message: str) -> bool:
        if not self.enabled:
            print(f"[DRY-RUN] Would send: {message}")
            return True
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect((self.ip, self.port))
                s.sendall(message.encode("utf-8"))
            print(f"📡 Sent: {message}")
            return True
        except Exception as exc:
            print(f"❌ TCP error: {exc}")
            return False


# ══════════════════════════════════════════════════════════════════
#  HSV TUNER  (run once to calibrate color thresholds)
# ══════════════════════════════════════════════════════════════════

class HSVTuner:
    """
    Interactive trackbar window.  Call run(), press 's' to save JSON.
    """

    WINDOW = "HSV Tuner"

    def __init__(self, cam_index: int, backend: int = cv2.CAP_MSMF,
                 output_path: str = "color_config.json"):
        self.cam_index   = cam_index
        self.backend     = backend
        self.output_path = output_path

    def run(self):
        cap = cv2.VideoCapture(self.cam_index, self.backend)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.cam_index}")

        cv2.namedWindow(self.WINDOW)
        for name, default, max_val in [
            ("H_lo", 8, 179), ("S_lo", 100, 255), ("V_lo", 100, 255),
            ("H_hi", 35, 179), ("S_hi", 255, 255), ("V_hi", 255, 255),
        ]:
            cv2.createTrackbar(name, self.WINDOW, default, max_val, lambda _: None)

        print("HSV Tuner  |  press 's' to save  |  press 'q' to quit")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            h_lo = cv2.getTrackbarPos("H_lo", self.WINDOW)
            s_lo = cv2.getTrackbarPos("S_lo", self.WINDOW)
            v_lo = cv2.getTrackbarPos("V_lo", self.WINDOW)
            h_hi = cv2.getTrackbarPos("H_hi", self.WINDOW)
            s_hi = cv2.getTrackbarPos("S_hi", self.WINDOW)
            v_hi = cv2.getTrackbarPos("V_hi", self.WINDOW)

            hsv  = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            mask = cv2.inRange(
                hsv,
                np.array([h_lo, s_lo, v_lo]),
                np.array([h_hi, s_hi, v_hi]),
            )
            cv2.imshow(self.WINDOW, cv2.bitwise_and(frame, frame, mask=mask))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                cfg = ColorConfig(
                    lower_h=h_lo, lower_s=s_lo, lower_v=v_lo,
                    upper_h=h_hi, upper_s=s_hi, upper_v=v_hi,
                )
                cfg.to_json(self.output_path)
                print(f"✅ Saved to {self.output_path}")
            elif key == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════
#  CSV LOGGER
# ══════════════════════════════════════════════════════════════════

class DetectionLogger:
    """Appends every stable detection to a CSV file."""

    def __init__(self, path: str = "detections.csv"):
        self.path = path
        self._file   = None
        self._writer = None

    def open(self):
        self._file   = open(self.path, "a", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=[
            "timestamp",
            "x_robot_mm", "y_robot_mm", "z_robot_mm",
            "angle_deg",  "pixel_size", "area",
        ])
        if Path(self.path).stat().st_size == 0:
            self._writer.writeheader()

    def log(self, result: DetectionResult):
        if self._writer:
            self._writer.writerow({
                "timestamp":    result.timestamp,
                "x_robot_mm":   round(result.x_robot_mm, 2),
                "y_robot_mm":   round(result.y_robot_mm, 2),
                "z_robot_mm":   round(result.z_robot_mm, 2),
                "angle_deg":    round(result.angle_deg,  2),
                "pixel_size":   round(result.pixel_size, 1),
                "area":         int(result.area),
            })
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()


# ══════════════════════════════════════════════════════════════════
#  OVERLAY RENDERER
# ══════════════════════════════════════════════════════════════════

class OverlayRenderer:
    """Draws all debug visuals onto a frame."""

    GREEN  = (0, 255,   0)
    RED    = (0,   0, 255)
    WHITE  = (255, 255, 255)
    YELLOW = (0, 220, 220)
    CYAN   = (255, 220,  0)

    def __init__(self):
        self._fps_timer  = time.time()
        self._fps_count  = 0
        self._fps_display= 0.0

    def _update_fps(self):
        self._fps_count += 1
        now = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._fps_display = self._fps_count / elapsed
            self._fps_count   = 0
            self._fps_timer   = now

    def draw(
        self,
        frame:     np.ndarray,
        result:    Optional[DetectionResult],
        stable:    bool,
        e6pos:     Optional[str],
    ) -> np.ndarray:
        out = frame.copy()
        self._update_fps()

        # ── FPS counter ──
        cv2.putText(
            out, f"FPS: {self._fps_display:.1f}",
            (10, out.shape[0] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.CYAN, 1,
        )

        if result is None:
            cv2.putText(out, "No detection", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.RED, 2)
            return out

        # ── bounding box ──
        color = self.GREEN if result.in_workspace else self.RED
        cv2.drawContours(out, [result.box], 0, color, 2)

        # ── centre dot ──
        cx_i, cy_i = int(result.cx_px), int(result.cy_px)
        cv2.circle(out, (cx_i, cy_i), 8, self.RED, -1)

        # ── angle line ──
        length = 40
        rad    = np.deg2rad(result.angle_deg)
        x2 = int(cx_i + length * np.cos(rad))
        y2 = int(cy_i - length * np.sin(rad))
        cv2.line(out, (cx_i, cy_i), (x2, y2), self.YELLOW, 2)

        # ── telemetry text ──
        lines = [
            f"Camera  (mm): {result.x_cam_mm:.1f}, {result.y_cam_mm:.1f}, {result.z_cam_mm:.1f}",
            f"Robot   (mm): {result.x_robot_mm:.1f}, {result.y_robot_mm:.1f}, {result.z_robot_mm:.1f}",
            f"Angle (deg) : {result.angle_deg:.1f}",
            f"Workspace   : {'✓ IN' if result.in_workspace else '✗ OUT'}",
            f"Stable      : {'✓ YES' if stable else '…waiting'}",
        ]
        for i, line in enumerate(lines):
            cv2.putText(out, line, (10, 30 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.WHITE, 1)

        if e6pos:
            cv2.putText(out, e6pos, (10, 30 + len(lines) * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.GREEN, 1)

        return out


# ══════════════════════════════════════════════════════════════════
#  CAMERA MANAGER
# ══════════════════════════════════════════════════════════════════

class CameraManager:
    """Opens and configures a VideoCapture; handles auto-detection."""

    def __init__(self, cfg: CameraConfig):
        self.cfg = cfg
        self.cap: Optional[cv2.VideoCapture] = None

    @staticmethod
    def list_working(max_index: int = 8, backend: int = cv2.CAP_MSMF) -> list[int]:
        working = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i, backend)
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    working.append(i)
            cap.release()
        return working

    def open(self) -> cv2.VideoCapture:
        cfg = self.cfg
        if cfg.auto_detect:
            cams = self.list_working(8, cfg.backend)
            if not cams:
                raise RuntimeError("No camera found.")
            print(f"✅ Available cameras: {cams}")
            idx = cfg.index if cfg.index in cams else cams[0]
        else:
            idx = cfg.index

        self.cap = cv2.VideoCapture(idx, cfg.backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera index: {idx}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cfg.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        print(f"📷 Opened camera {idx}  ({cfg.width}×{cfg.height})")
        return self.cap

    def release(self):
        if self.cap:
            self.cap.release()


# ══════════════════════════════════════════════════════════════════
#  VISION PIPELINE  (top-level orchestrator)
# ══════════════════════════════════════════════════════════════════

class VisionPipeline:
    """
    Wires all components together and runs the main loop.

    Parameters
    ----------
    cam_cfg    : CameraConfig
    robot_cfg  : RobotConfig
    color_cfg  : ColorConfig
    cube_size_m: float  – physical size of the cube in metres
    log_path   : str or None  – set to a path to enable CSV logging
    send_robot : bool   – enable TCP transmission to robot
    stability  : (frames, threshold_mm) tuple
    """

    def __init__(
        self,
        cam_cfg:     CameraConfig  = CameraConfig(),
        robot_cfg:   RobotConfig   = RobotConfig(),
        color_cfg:   ColorConfig   = ColorConfig(),
        cube_size_m: float         = 0.05,
        log_path:    Optional[str] = None,
        send_robot:  bool          = False,
        stability:   tuple         = (5, 5.0),
    ):
        self.cam_mgr     = CameraManager(cam_cfg)
        self.detector    = CubeDetector(color_cfg)
        self.transformer = CoordinateTransformer(cam_cfg, robot_cfg, cube_size_m)
        self.tracker     = KalmanTracker()
        self.guard       = StabilityGuard(*stability)
        self.renderer    = OverlayRenderer()
        self.bridge      = RobotBridge(
            robot_cfg.tcp_ip, robot_cfg.tcp_port, enabled=send_robot
        )
        self.logger: Optional[DetectionLogger] = None
        if log_path:
            self.logger = DetectionLogger(log_path)

    # ── public entry point ──────────────────────────────────────────

    def run(self):
        cap = self.cam_mgr.open()
        if self.logger:
            self.logger.open()

        print("🚀 Pipeline running  |  press 'q' to quit")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("⚠️  Frame grab failed – exiting.")
                    break

                result, mask = self.detector.detect_with_mask(frame)
                e6pos        = None
                stable       = False

                if result is not None:
                    # Smooth the pixel-space centre before transforming
                    result.cx_px, result.cy_px = self.tracker.update(
                        result.cx_px, result.cy_px
                    )
                    result = self.transformer.transform(result)

                    if result is not None and result.in_workspace:
                        e6pos  = self.transformer.to_e6pos(result)
                        stable = self.guard.is_stable(result)

                        if stable:
                            print("E6POS:", e6pos)
                            self.bridge.send(e6pos)
                            if self.logger:
                                self.logger.log(result)
                else:
                    self.tracker.reset()
                    self.guard.reset()

                vis = self.renderer.draw(frame, result, stable, e6pos)
                cv2.imshow("Vision → KUKA", vis)
                cv2.imshow("Mask",          mask)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

        finally:
            self.cam_mgr.release()
            cv2.destroyAllWindows()
            if self.logger:
                self.logger.close()
            print("🛑 Pipeline stopped.")


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # ── Load configs from JSON if files exist, else use defaults ──
    COLOR_JSON  = "color_config.json"
    CAM_JSON    = "camera_config.json"
    ROBOT_JSON  = "robot_config.json"

    cam_cfg   = CameraConfig.from_json(CAM_JSON)   if Path(CAM_JSON).exists()   else CameraConfig()
    robot_cfg = RobotConfig.from_json(ROBOT_JSON)  if Path(ROBOT_JSON).exists() else RobotConfig()
    color_cfg = ColorConfig.from_json(COLOR_JSON)  if Path(COLOR_JSON).exists() else ColorConfig()

    # ── Uncomment to run HSV tuner before starting pipeline ──
    HSVTuner(cam_cfg.index, cam_cfg.backend, COLOR_JSON).run()

    pipeline = VisionPipeline(
        cam_cfg     = cam_cfg,
        robot_cfg   = robot_cfg,
        color_cfg   = color_cfg,
        cube_size_m = 0.05,
        log_path    = "detections.csv",   # set to None to disable
        send_robot  = False,              # ← set True to enable TCP
        stability   = (5, 5.0),           # frames, mm threshold
    )
    pipeline.run()
    
    