"""
kuka_vision.py
==============
OOP vision pipeline for orange cube detection → KUKA KR20 R1810 pick & place.

Uses EkiManager library for robot communication (PC = TCP client,
robot KRL server listens). Commands: gotojointpos, gotoframe,
gripopen, gripclose — all handled by the tested EkiManager layer.

Sequence
--------
1.  PC connects to robot KRL server via EkiManager
2.  Robot moves to HOME position
3.  Camera detects cube → computes E6POS
4.  User confirms in terminal before robot moves
5.  Pick & place sequence executes
6.  Repeat from step 2
"""

import cv2
import numpy as np
import json
import time
import csv
import sys
import threading
import traceback
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from enum import Enum, auto

from PIL import Image, ImageTk

from EkiManager import EkiManager
from JointPosition import JointPosition


# ══════════════════════════════════════════════════════════════════
#  ENUMS
# ══════════════════════════════════════════════════════════════════

class RobotState(Enum):
    IDLE        = auto()
    HOMING      = auto()
    DETECTING   = auto()
    APPROACHING = auto()
    PICKING     = auto()
    LIFTING     = auto()
    PLACING     = auto()
    RETURNING   = auto()
    ERROR       = auto()


class PipelinePhase(Enum):
    IDLE       = auto()   # Camera detecting, user can capture
    CONFIRMING = auto()   # Target captured, awaiting user confirm
    EXECUTING  = auto()   # Robot executing pick-and-place
    FOLLOWING  = auto()   # Robot continuously follows detected cube


# ══════════════════════════════════════════════════════════════════
#  CONFIG DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class CameraConfig:
    index: int          = 0
    width: int          = 640
    height: int         = 480
    fx: float           = 800.0
    fy: float           = 800.0
    cx: Optional[float] = None
    cy: Optional[float] = None
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
    # ── Camera-to-robot rigid transform ──
    cam_offset_x: float  =  600.0   # mm
    cam_offset_y: float  =    0.0
    cam_offset_z: float  =  800.0

    # ── Fixed pick height (mm from robot base) ──
    # Set this to the table surface Z in robot coordinates.
    # The pinhole Z estimate is unreliable — this value is used instead.
    pick_height_mm: float = 20.0

    # ── Fixed orientation sent in every E6POS ──
    robot_a: float       =    0.0
    robot_b: float       =   90.0

    # ── Workspace bounds (mm from base frame) — camera pixels map linearly ──
    workspace_x: tuple   = (0.0, 500.0)
    workspace_y: tuple   = (0.0, 500.0)

    # ── Robot TCP endpoint (PC connects TO robot as client) ──
    tcp_ip: str          = "192.168.1.1"
    tcp_port: int        = 54610

    # ── Post-command delays (seconds) — extra settle time after EkiManager response ──
    delay_joint_move: float  = 0.5    # wait after joint move response
    delay_linear_move: float = 0.3    # wait after linear move response
    delay_gripper: float     = 0.5    # wait after gripper response
    delay_between_cmds: float = 0.1   # gap between consecutive sends

    # ── Pick & place geometry ──
    approach_clearance_mm: float = 80.0
    pick_z_offset_mm: float      =  0.0
    place_x_mm: float            = 500.0
    place_y_mm: float            = 300.0
    place_z_mm: float            = 200.0
    place_a_mm: float            = 180.0
    place_b_mm: float            =   0.0
    place_c_mm: float            =   0.0

    # ── Home joint angles (degrees) — KR20 R1810 ──
    home_a1: float =   0.0
    home_a2: float = -90.0
    home_a3: float =  90.0
    home_a4: float =   0.0
    home_a5: float =  90.0
    home_a6: float =   0.0

    @classmethod
    def from_json(cls, path: str) -> "RobotConfig":
        with open(path) as f:
            data = json.load(f)
            data["workspace_x"] = tuple(data["workspace_x"])
            data["workspace_y"] = tuple(data["workspace_y"])
            return cls(**data)

    def to_json(self, path: str):
        d = asdict(self)
        d["workspace_x"] = list(d["workspace_x"])
        d["workspace_y"] = list(d["workspace_y"])
        with open(path, "w") as f:
            json.dump(d, f, indent=2)


@dataclass
class ColorConfig:
    lower_h: int     =   5
    lower_s: int     =  80
    lower_v: int     =  80
    upper_h: int     =  38
    upper_s: int     = 255
    upper_v: int     = 255
    min_area: int    = 800
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
    cx_px: float
    cy_px: float
    angle_deg: float
    pixel_size: float
    area: float
    box: np.ndarray
    x_cam_mm: float    = 0.0
    y_cam_mm: float    = 0.0
    z_cam_mm: float    = 0.0
    x_robot_mm: float  = 0.0
    y_robot_mm: float  = 0.0
    z_robot_mm: float  = 0.0
    robot_a: float     = 0.0
    robot_b: float     = 90.0
    in_workspace: bool = False
    timestamp: float   = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════
#  ROBOT CONTROLLER
#  High-level pick & place using EkiManager library.
#  EkiManager waits for KRL response; optional post-command delays
#  can be tuned in RobotConfig if extra settle time is needed.
# ══════════════════════════════════════════════════════════════════

class RobotController:

    def __init__(self, robot_cfg: RobotConfig, eki: EkiManager):
        self.cfg   = robot_cfg
        self.eki   = eki
        self.state = RobotState.IDLE

    def _set_state(self, state: RobotState):
        self.state = state
        print(f"  [{state.name}]")

    def _wait_joint(self):
        """Optional settle time after joint move."""
        if self.cfg.delay_joint_move > 0:
            time.sleep(self.cfg.delay_joint_move)

    def _wait_linear(self):
        """Optional settle time after linear move."""
        if self.cfg.delay_linear_move > 0:
            time.sleep(self.cfg.delay_linear_move)

    def _wait_gripper(self):
        """Optional settle time after gripper action."""
        if self.cfg.delay_gripper > 0:
            time.sleep(self.cfg.delay_gripper)

    def _pause(self):
        """Small gap between consecutive sends."""
        if self.cfg.delay_between_cmds > 0:
            time.sleep(self.cfg.delay_between_cmds)

    # ── Motion commands ───────────────────────────────────────────

    def go_home(self) -> bool:
        self._set_state(RobotState.HOMING)
        c = self.cfg
        home_pos = JointPosition(
            [c.home_a1, c.home_a2, c.home_a3,
             c.home_a4, c.home_a5, c.home_a6],
            [0, 0, 0, 0, 0, 0],
        )
        try:
            self.eki.goToJointPos(home_pos)
            self._wait_joint()
            self._set_state(RobotState.IDLE)
            return True
        except Exception as exc:
            print(f"  Home failed: {exc}")
            self._set_state(RobotState.ERROR)
            return False

    def move_linear(self, x, y, z, a, b, c) -> bool:
        try:
            self.eki.goToFrame([x, y, z, a, b, c])
            self._wait_linear()
            return True
        except Exception as exc:
            print(f"  Linear move failed: {exc}")
            self._set_state(RobotState.ERROR)
            return False

    def gripper_open(self) -> bool:
        try:
            self.eki.gripOpen()
            self._wait_gripper()
            return True
        except Exception as exc:
            print(f"  Gripper open failed: {exc}")
            return False

    def gripper_close(self) -> bool:
        try:
            self.eki.gripClose()
            self._wait_gripper()
            return True
        except Exception as exc:
            print(f"  Gripper close failed: {exc}")
            return False

    # ── Pick & place steps ────────────────────────────────────────

    def approach_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.APPROACHING)
        c = self.cfg
        return self.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.approach_clearance_mm,
            det.robot_a, det.robot_b, det.angle_deg,
        )

    def pick_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.PICKING)
        c = self.cfg

        # 1 — Open gripper
        if not self.gripper_open():
            self._set_state(RobotState.ERROR)
            return False
        self._pause()

        # 2 — Lower to pick height
        if not self.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.pick_z_offset_mm,
            det.robot_a, det.robot_b, det.angle_deg,
        ):
            self._set_state(RobotState.ERROR)
            return False
        self._pause()

        # 3 — Close gripper
        if not self.gripper_close():
            self._set_state(RobotState.ERROR)
            return False

        return True

    def lift_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.LIFTING)
        c = self.cfg
        return self.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.approach_clearance_mm,
            det.robot_a, det.robot_b, det.angle_deg,
        )

    def place_cube(self) -> bool:
        self._set_state(RobotState.PLACING)
        c = self.cfg

        # 1 — Move above place
        if not self.move_linear(
            c.place_x_mm, c.place_y_mm,
            c.place_z_mm + c.approach_clearance_mm,
            c.place_a_mm, c.place_b_mm, c.place_c_mm,
        ):
            self._set_state(RobotState.ERROR)
            return False
        self._pause()

        # 2 — Lower to place
        if not self.move_linear(
            c.place_x_mm, c.place_y_mm, c.place_z_mm,
            c.place_a_mm, c.place_b_mm, c.place_c_mm,
        ):
            self._set_state(RobotState.ERROR)
            return False
        self._pause()

        # 3 — Release
        if not self.gripper_open():
            self._set_state(RobotState.ERROR)
            return False

        return True

    # ── Full sequence ─────────────────────────────────────────────

    def execute_pick_and_place(self, det: DetectionResult) -> bool:
        print("\n--- PICK & PLACE SEQUENCE ---")

        steps = [
            ("Approach", lambda: self.approach_cube(det)),
            ("Pick",     lambda: self.pick_cube(det)),
            ("Lift",     lambda: self.lift_cube(det)),
            ("Place",    lambda: self.place_cube()),
            ("Return",   lambda: self._return_home()),
        ]

        for name, step_fn in steps:
            print(f"  > {name}")
            self._pause()
            if not step_fn():
                print(f"  X Step '{name}' FAILED -- attempting safe recovery")
                self.go_home()
                return False

        self._set_state(RobotState.IDLE)
        print("--- SEQUENCE COMPLETE ---\n")
        return True

    def _return_home(self) -> bool:
        self._set_state(RobotState.RETURNING)
        return self.go_home()


# ══════════════════════════════════════════════════════════════════
#  KALMAN TRACKER
# ══════════════════════════════════════════════════════════════════

class KalmanTracker:
    def __init__(self, process_noise: float = 1e-2, measure_noise: float = 1e1):
        self.kf = cv2.KalmanFilter(4, 2)
        dt = 1.0
        self.kf.transitionMatrix = np.array([
            [1, 0, dt,  0],
            [0, 1,  0, dt],
            [0, 0,  1,  0],
            [0, 0,  0,  1],
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
            self.kf.statePre = np.array([[cx], [cy], [0.0], [0.0]], dtype=np.float32)
            self._initialized = True
        self.kf.predict()
        corrected = self.kf.correct(measurement)
        return float(corrected[0, 0]), float(corrected[1, 0])

    def reset(self):
        self._initialized = False


# ══════════════════════════════════════════════════════════════════
#  DETECTORS — Strategy pattern for multi-object detection
# ══════════════════════════════════════════════════════════════════

class HSVShapeDetector:
    """
    General-purpose HSV color + shape detector.
    Configurable aspect ratio range allows it to detect cubes (square)
    or elongated objects like screwdrivers.
    """

    def __init__(self, color_cfg: ColorConfig,
                 min_solidity: float = 0.65,
                 min_aspect: float = 0.30,
                 max_aspect: float = 1.0):
        self.color_cfg    = color_cfg
        self.min_solidity = min_solidity
        self.min_aspect   = min_aspect
        self.max_aspect   = max_aspect
        self.kernel       = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (color_cfg.kernel_size, color_cfg.kernel_size),
        )
        self.clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))

    def uses_hsv(self) -> bool:
        return True

    def build_mask(self, frame: np.ndarray) -> np.ndarray:
        blurred = cv2.GaussianBlur(frame, (7, 7), 0)
        hsv     = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v = self.clahe.apply(v)
        hsv = cv2.merge([h, s, v])
        mask = cv2.inRange(hsv, self.color_cfg.lower(), self.color_cfg.upper())
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  self.kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel, iterations=3)
        return mask

    def detect_with_mask(
        self, frame: np.ndarray
    ) -> tuple[Optional[DetectionResult], np.ndarray]:
        mask = self.build_mask(frame)
        contours, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, mask

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.color_cfg.min_area:
                continue

            hull      = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            solidity  = area / hull_area if hull_area > 0 else 0
            if solidity < self.min_solidity:
                continue

            rect = cv2.minAreaRect(c)
            (cx, cy), (rw, rh), angle = rect
            aspect = min(rw, rh) / max(rw, rh) if max(rw, rh) > 0 else 0
            if aspect < self.min_aspect or aspect > self.max_aspect:
                continue

            score = area * solidity * (0.5 + 0.5 * aspect)
            candidates.append((score, c, rect, area))

        if not candidates:
            return None, mask

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, _, rect, area = candidates[0]

        (cx, cy), (rw, rh), angle = rect
        if rw < rh:
            angle += 90
        angle = angle % 90

        return DetectionResult(
            cx_px      = cx,
            cy_px      = cy,
            angle_deg  = angle,
            pixel_size = max(rw, rh),
            area       = area,
            box        = np.intp(cv2.boxPoints(rect)),
        ), mask


class ArUcoDetector:
    """
    ArUco marker detector using cv2.aruco module.
    Dictionary: DICT_6X6_250.
    Computes distance from camera using pose estimation.
    """

    def __init__(self, marker_size_m: float = 0.05,
                 cam_cfg: CameraConfig = None):
        self.color_cfg = None  # no HSV config
        self.marker_size_m = marker_size_m
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_6X6_250)
        self._aruco_params = cv2.aruco.DetectorParameters()

        # Camera matrix for pose estimation
        cfg = cam_cfg or CameraConfig()
        ppx, ppy = cfg.principal_point()
        self._camera_matrix = np.array([
            [cfg.fx,    0, ppx],
            [   0, cfg.fy, ppy],
            [   0,    0,     1],
        ], dtype=np.float64)
        self._dist_coeffs = np.zeros((4, 1))  # assume no lens distortion
        self.last_distance_mm = 0.0  # exposed for overlay

    def uses_hsv(self) -> bool:
        return False

    def detect_with_mask(
        self, frame: np.ndarray
    ) -> tuple[Optional[DetectionResult], np.ndarray]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, self._aruco_dict, parameters=self._aruco_params)

        mask = np.zeros(gray.shape, dtype=np.uint8)

        if ids is None or len(ids) == 0:
            self.last_distance_mm = 0.0
            return None, mask

        # Use the first detected marker
        marker_corners = corners[0][0]  # shape (4, 2)
        cv2.fillPoly(mask, [np.intp(marker_corners)], 255)

        # Centre = mean of 4 corners
        cx = float(np.mean(marker_corners[:, 0]))
        cy = float(np.mean(marker_corners[:, 1]))

        # Angle from top-left to top-right edge
        dx = marker_corners[1][0] - marker_corners[0][0]
        dy = marker_corners[1][1] - marker_corners[0][1]
        angle = float(np.degrees(np.arctan2(-dy, dx))) % 360

        # Bounding box
        rect = cv2.minAreaRect(np.intp(marker_corners))
        (_, _), (rw, rh), _ = rect
        box = np.intp(cv2.boxPoints(rect))
        area = float(rw * rh)

        # ── Pose estimation: compute distance from camera ──
        rvecs, tvecs, _ = cv2.aruco.estimatePoseSingleMarkers(
            corners[0:1], self.marker_size_m,
            self._camera_matrix, self._dist_coeffs)
        tvec = tvecs[0][0]  # translation vector [x, y, z] in metres
        distance_m = float(np.linalg.norm(tvec))
        self.last_distance_mm = distance_m * 1000.0

        result = DetectionResult(
            cx_px      = cx,
            cy_px      = cy,
            angle_deg  = angle % 90,
            pixel_size = max(rw, rh),
            area       = area,
            box        = box,
        )
        # Store camera-frame Z from pose estimation
        result.z_cam_mm = self.last_distance_mm

        return result, mask


# ── Face Detector ─────────────────────────────────────────────────

class FaceDetector:
    """
    Human face detector using OpenCV DNN (res10_300x300 caffe model)
    with Haar cascade fallback if model files are missing.
    """

    # DNN model files (ship with OpenCV contrib or download once)
    _DNN_PROTO = "deploy.prototxt"
    _DNN_MODEL = "res10_300x300_ssd_iter_140000.caffemodel"

    def __init__(self):
        self.color_cfg = None  # no HSV config
        self._use_dnn = False

        # Try DNN first (more accurate)
        try:
            from pathlib import Path
            proto = Path(__file__).parent / self._DNN_PROTO
            model = Path(__file__).parent / self._DNN_MODEL
            if proto.exists() and model.exists():
                self._net = cv2.dnn.readNetFromCaffe(str(proto), str(model))
                self._use_dnn = True
        except Exception:
            pass

        # Fallback: Haar cascade (always available in OpenCV)
        if not self._use_dnn:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(cascade_path)

    def uses_hsv(self) -> bool:
        return False

    def _detect_dnn(self, frame: np.ndarray):
        """DNN-based face detection — higher accuracy."""
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 1.0, (300, 300),
            (104.0, 177.0, 123.0))
        self._net.setInput(blob)
        detections = self._net.forward()

        best = None
        best_conf = 0.0
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence < 0.5:
                continue
            if confidence > best_conf:
                best_conf = confidence
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                best = box.astype(int)

        return best  # (x1, y1, x2, y2) or None

    def _detect_haar(self, frame: np.ndarray):
        """Haar cascade fallback — faster but less accurate."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self._cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None

        # Pick largest face
        areas = [w * h for (_, _, w, h) in faces]
        idx = int(np.argmax(areas))
        x, y, w, h = faces[idx]
        return np.array([x, y, x + w, y + h])

    def detect_with_mask(
        self, frame: np.ndarray
    ) -> tuple[Optional[DetectionResult], np.ndarray]:
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)

        if self._use_dnn:
            box = self._detect_dnn(frame)
        else:
            box = self._detect_haar(frame)

        if box is None:
            return None, mask

        x1, y1, x2, y2 = box
        # Clamp to frame bounds
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        cv2.rectangle(mask, (x1, y1), (x2, y2), 255, -1)

        cx = float(x1 + x2) / 2.0
        cy = float(y1 + y2) / 2.0
        fw = float(x2 - x1)
        fh = float(y2 - y1)
        area = fw * fh

        # Build a 4-point box for DetectionResult
        rect_box = np.array([
            [x1, y1], [x2, y1], [x2, y2], [x1, y2]
        ], dtype=np.intp)

        return DetectionResult(
            cx_px      = cx,
            cy_px      = cy,
            angle_deg  = 0.0,   # faces have no rotation in this context
            pixel_size = max(fw, fh),
            area       = area,
            box        = rect_box,
        ), mask


# ── Detector presets ──────────────────────────────────────────────

DETECTOR_PRESETS = {
    "Orange Cube": {
        "class": HSVShapeDetector,
        "color_cfg": ColorConfig(
            lower_h=5, lower_s=80, lower_v=80,
            upper_h=38, upper_s=255, upper_v=255,
        ),
        "min_solidity": 0.65,
        "min_aspect": 0.30,
        "max_aspect": 1.0,
    },
    "Black Cube": {
        "class": HSVShapeDetector,
        "color_cfg": ColorConfig(
            lower_h=0, lower_s=0, lower_v=0,
            upper_h=179, upper_s=80, upper_v=60,
        ),
        "min_solidity": 0.65,
        "min_aspect": 0.30,
        "max_aspect": 1.0,
    },
    "ArUco Tag": {
        "class": ArUcoDetector,
    },
    "Human Face": {
        "class": FaceDetector,
    },
}


def build_detector(name: str, cam_cfg: CameraConfig = None):
    """Instantiate a detector from the presets dictionary."""
    preset = DETECTOR_PRESETS[name]
    cls = preset["class"]
    if cls is ArUcoDetector:
        return ArUcoDetector(cam_cfg=cam_cfg)
    if cls is FaceDetector:
        return FaceDetector()
    return HSVShapeDetector(
        color_cfg    = preset["color_cfg"],
        min_solidity = preset.get("min_solidity", 0.65),
        min_aspect   = preset.get("min_aspect", 0.30),
        max_aspect   = preset.get("max_aspect", 1.0),
    )


# Backwards-compatible alias
CubeDetector = HSVShapeDetector


# ══════════════════════════════════════════════════════════════════
#  COORDINATE TRANSFORMER
# ══════════════════════════════════════════════════════════════════

class CoordinateTransformer:
    """
    Direct linear mapping: camera pixel coordinates → workspace mm.

    The full camera frame (0..width, 0..height) maps linearly to the
    workspace rectangle defined by workspace_x and workspace_y in
    RobotConfig.  Z is still estimated via the pinhole/cube-size model
    so the robot knows the approach height.
    """

    def __init__(self, cam_cfg: CameraConfig, robot_cfg: RobotConfig,
                 cube_size_m: float = 0.05):
        self.cam_cfg     = cam_cfg
        self.robot_cfg   = robot_cfg
        self.cube_size_m = cube_size_m

    def transform(self, result: DetectionResult,
                  frame_w: int = None, frame_h: int = None
                  ) -> Optional[DetectionResult]:
        if result.pixel_size <= 1:
            return None

        r = self.robot_cfg
        c = self.cam_cfg

        # Use actual captured frame size (may differ from config)
        w = frame_w if frame_w is not None else c.width
        h = frame_h if frame_h is not None else c.height

        # ── Z: fixed pick height for robot motion ──
        result.z_robot_mm = r.pick_height_mm

        # ── Z distance from camera (pinhole estimate) ──
        # If detector already set z_cam_mm (e.g. ArUco pose), keep it.
        # Otherwise estimate from object pixel size and known real size.
        if result.z_cam_mm <= 0.0 and result.pixel_size > 1:
            result.z_cam_mm = (self.cube_size_m * 1000.0 * c.fx) / result.pixel_size

        # ── X, Y: linear pixel → workspace mapping ──
        wx_lo, wx_hi = r.workspace_x
        wy_lo, wy_hi = r.workspace_y

        # Normalise pixel position to [0, 1] using actual frame size
        nx = result.cx_px / w
        ny = result.cy_px / h

        result.x_robot_mm = wx_lo + nx * (wx_hi - wx_lo)
        # Camera Y is top-down, robot Y typically increases upward → flip
        result.y_robot_mm = wy_hi - ny * (wy_hi - wy_lo)

        # Camera-frame values (informational)
        result.x_cam_mm = result.x_robot_mm - r.cam_offset_x
        result.y_cam_mm = result.y_robot_mm - r.cam_offset_y

        result.in_workspace = (
            wx_lo <= result.x_robot_mm <= wx_hi
            and wy_lo <= result.y_robot_mm <= wy_hi
        )
        return result

    def to_e6pos(self, result: DetectionResult) -> str:
        return (
            f"{{X {result.x_robot_mm:.2f}, Y {result.y_robot_mm:.2f}, "
            f"Z {result.z_robot_mm:.2f}, A {result.robot_a:.2f}, "
            f"B {result.robot_b:.2f}, C {result.angle_deg:.2f}}}"
        )


# ══════════════════════════════════════════════════════════════════
#  STABILITY GUARD
# ══════════════════════════════════════════════════════════════════

class StabilityGuard:
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
        dist = np.linalg.norm(np.array(pos) - np.array(self._history[-1]))
        self._stable_count = self._stable_count + 1 if dist < self.threshold_mm else 1
        self._history = [pos]
        return self._stable_count >= self.required_frames

    def reset(self):
        self._history      = []
        self._stable_count = 0


# ══════════════════════════════════════════════════════════════════
#  CSV LOGGER
# ══════════════════════════════════════════════════════════════════

class DetectionLogger:
    def __init__(self, path: str = "detections.csv"):
        self.path    = path
        self._file   = None
        self._writer = None

    def open(self):
        self._file   = open(self.path, "a", newline="")
        self._writer = csv.DictWriter(self._file, fieldnames=[
            "timestamp", "x_robot_mm", "y_robot_mm", "z_robot_mm",
            "angle_deg", "pixel_size", "area",
        ])
        if Path(self.path).stat().st_size == 0:
            self._writer.writeheader()

    def log(self, result: DetectionResult):
        if self._writer:
            self._writer.writerow({
                "timestamp":  result.timestamp,
                "x_robot_mm": round(result.x_robot_mm, 2),
                "y_robot_mm": round(result.y_robot_mm, 2),
                "z_robot_mm": round(result.z_robot_mm, 2),
                "angle_deg":  round(result.angle_deg,  2),
                "pixel_size": round(result.pixel_size, 1),
                "area":       int(result.area),
            })
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()


# ══════════════════════════════════════════════════════════════════
#  OVERLAY RENDERER
# ══════════════════════════════════════════════════════════════════

class OverlayRenderer:
    GREEN  = (0, 255,   0)
    RED    = (0,   0, 255)
    WHITE  = (255, 255, 255)
    YELLOW = (0, 220, 220)
    CYAN   = (255, 220,   0)
    ORANGE = (0, 140, 255)

    def __init__(self):
        self._fps_timer   = time.time()
        self._fps_count   = 0
        self._fps_display = 0.0

    def _update_fps(self):
        self._fps_count += 1
        now     = time.time()
        elapsed = now - self._fps_timer
        if elapsed >= 1.0:
            self._fps_display = self._fps_count / elapsed
            self._fps_count   = 0
            self._fps_timer   = now

    def draw(
        self,
        frame:            np.ndarray,
        result:           Optional[DetectionResult],
        stable:           bool,
        e6pos:            Optional[str],
        robot_state:      RobotState = RobotState.IDLE,
        awaiting_confirm: bool = False,
        detect_mode:      str = "Orange Cube",
    ) -> np.ndarray:
        out = frame.copy()
        self._update_fps()

        # FPS
        cv2.putText(out, f"FPS: {self._fps_display:.1f}",
                    (10, out.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.CYAN, 1)

        # Mode label (top-left, small)
        cv2.putText(out, f"[{detect_mode}]", (10, out.shape[0] - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.CYAN, 1)

        # Robot state banner (top-right)
        state_color = self.GREEN if robot_state == RobotState.IDLE else self.ORANGE
        cv2.putText(out, f"ROBOT: {robot_state.name}",
                    (out.shape[1] - 230, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, state_color, 2)

        # Confirmation banner (top-center) — pulsing when target locked
        if awaiting_confirm:
            pulse = 0.5 + 0.5 * np.sin(time.time() * 4.0)

            label = "TARGET LOCKED - Confirm or Skip"
            text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            tx = (out.shape[1] - text_size[0]) // 2

            cv2.rectangle(out, (tx - 12, 36), (tx + text_size[0] + 12, 76),
                          (0, 0, 0), -1)
            border_color = (0, int(100 * pulse), int(255 * pulse))
            cv2.rectangle(out, (tx - 12, 36), (tx + text_size[0] + 12, 76),
                          border_color, 2)

            text_color = (0, int(100 + 40 * pulse), int(140 + 115 * pulse))
            cv2.putText(out, label, (tx, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, text_color, 2)

        if result is None:
            if detect_mode == "Human Face":
                self._draw_face_idle(out)
            else:
                cv2.putText(out, "No detection", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.RED, 2)
            return out

        # ── Mode-specific overlays ──
        if detect_mode == "ArUco Tag":
            self._draw_aruco(out, result, stable, e6pos, awaiting_confirm)
        elif detect_mode == "Human Face":
            self._draw_face(out, result, stable, e6pos, awaiting_confirm)
        else:
            self._draw_default(out, result, stable, e6pos, awaiting_confirm)

        return out

    # ── Default overlay (cubes, screwdriver) ─────────────────────

    def _draw_default(self, out, result, stable, e6pos, awaiting_confirm):
        color = self.GREEN if result.in_workspace else self.RED
        cv2.drawContours(out, [result.box], 0, color, 2)

        if awaiting_confirm:
            pulse = 0.5 + 0.5 * np.sin(time.time() * 4.0)
            pulse_color = (0, int(140 * pulse), int(255 * pulse))
            cv2.drawContours(out, [result.box], 0, pulse_color, 3)

        cx_i, cy_i = int(result.cx_px), int(result.cy_px)
        cv2.circle(out, (cx_i, cy_i), 8, self.RED, -1)

        rad = np.deg2rad(result.angle_deg)
        cv2.line(out, (cx_i, cy_i),
                 (int(cx_i + 40 * np.cos(rad)), int(cy_i - 40 * np.sin(rad))),
                 self.YELLOW, 2)

        # Distance label near the detected object
        if result.z_cam_mm > 0:
            cv2.putText(out, f"Dist: {result.z_cam_mm:.0f} mm",
                        (cx_i - 40, cy_i - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.CYAN, 2)

        self._draw_telemetry(out, result, stable, e6pos)

    # ── ArUco overlay (coordinate axes) ──────────────────────────

    def _draw_aruco(self, out, result, stable, e6pos, awaiting_confirm):
        # Draw marker outline
        color = self.GREEN if result.in_workspace else self.RED
        cv2.drawContours(out, [result.box], 0, color, 2)

        if awaiting_confirm:
            pulse = 0.5 + 0.5 * np.sin(time.time() * 4.0)
            pulse_color = (0, int(140 * pulse), int(255 * pulse))
            cv2.drawContours(out, [result.box], 0, pulse_color, 3)

        cx_i, cy_i = int(result.cx_px), int(result.cy_px)
        axis_len = int(result.pixel_size * 0.6)
        rad = np.deg2rad(result.angle_deg)

        # X axis — Red
        x_end = (int(cx_i + axis_len * np.cos(rad)),
                 int(cy_i - axis_len * np.sin(rad)))
        cv2.arrowedLine(out, (cx_i, cy_i), x_end, (0, 0, 255), 2,
                        tipLength=0.15)
        cv2.putText(out, "X", (x_end[0] + 5, x_end[1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Y axis — Green (perpendicular to X)
        y_end = (int(cx_i + axis_len * np.cos(rad + np.pi / 2)),
                 int(cy_i - axis_len * np.sin(rad + np.pi / 2)))
        cv2.arrowedLine(out, (cx_i, cy_i), y_end, (0, 255, 0), 2,
                        tipLength=0.15)
        cv2.putText(out, "Y", (y_end[0] + 5, y_end[1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Z axis — Blue (coming out of plane, drawn as a dot + short line)
        cv2.circle(out, (cx_i, cy_i), 5, (255, 0, 0), -1)
        cv2.circle(out, (cx_i, cy_i), 10, (255, 0, 0), 2)
        cv2.putText(out, "Z", (cx_i + 12, cy_i - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

        # Origin label
        cv2.putText(out, "O", (cx_i - 20, cy_i + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.WHITE, 1)

        # Corner dots on marker
        for pt in result.box:
            cv2.circle(out, tuple(pt), 4, self.CYAN, -1)

        # Distance from camera (from z_cam_mm set by ArUcoDetector)
        dist_mm = result.z_cam_mm
        if dist_mm > 0:
            dist_label = f"Dist: {dist_mm:.0f} mm"
            cv2.putText(out, dist_label, (cx_i - 40, cy_i + axis_len + 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.CYAN, 2)

        self._draw_telemetry(out, result, stable, e6pos)

    # ── Face biometrics overlay ──────────────────────────────────

    def _draw_face_idle(self, out):
        """Scanning animation when no face is detected."""
        h, w = out.shape[:2]
        t = time.time()
        scan_y = int((h * 0.3) + (h * 0.4) * (0.5 + 0.5 * np.sin(t * 2.0)))

        # Scan line
        alpha = 0.3
        overlay = out.copy()
        cv2.line(overlay, (0, scan_y), (w, scan_y), (0, 255, 0), 1)
        cv2.addWeighted(overlay, alpha, out, 1 - alpha, 0, out)

        # Crosshair at center
        cx, cy = w // 2, h // 2
        gap = 20
        cv2.line(out, (cx - 40, cy), (cx - gap, cy), self.GREEN, 1)
        cv2.line(out, (cx + gap, cy), (cx + 40, cy), self.GREEN, 1)
        cv2.line(out, (cx, cy - 40), (cx, cy - gap), self.GREEN, 1)
        cv2.line(out, (cx, cy + gap), (cx, cy + 40), self.GREEN, 1)

        cv2.putText(out, "SCANNING...", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.GREEN, 2)

    def _draw_face(self, out, result, stable, e6pos, awaiting_confirm):
        """Biometrics-themed overlay for face detection."""
        cx_i, cy_i = int(result.cx_px), int(result.cy_px)
        t = time.time()

        # Get face bounding box dimensions
        x1, y1 = result.box[0]
        x2, y2 = result.box[2]
        fw, fh = int(x2 - x1), int(y2 - y1)

        # Corner brackets (biometric scan frame)
        corner_len = max(20, int(min(fw, fh) * 0.2))
        thickness = 2

        # Pulsing green when stable, amber when scanning
        if stable:
            bracket_color = self.GREEN
        else:
            pulse = 0.5 + 0.5 * np.sin(t * 3.0)
            bracket_color = (0, int(200 + 55 * pulse), int(100 * pulse))

        if awaiting_confirm:
            pulse = 0.5 + 0.5 * np.sin(t * 4.0)
            bracket_color = (0, int(140 * pulse), int(255 * pulse))

        # Top-left corner
        cv2.line(out, (x1, y1), (x1 + corner_len, y1), bracket_color, thickness)
        cv2.line(out, (x1, y1), (x1, y1 + corner_len), bracket_color, thickness)
        # Top-right corner
        cv2.line(out, (x2, y1), (x2 - corner_len, y1), bracket_color, thickness)
        cv2.line(out, (x2, y1), (x2, y1 + corner_len), bracket_color, thickness)
        # Bottom-left corner
        cv2.line(out, (x1, y2), (x1 + corner_len, y2), bracket_color, thickness)
        cv2.line(out, (x1, y2), (x1, y2 - corner_len), bracket_color, thickness)
        # Bottom-right corner
        cv2.line(out, (x2, y2), (x2 - corner_len, y2), bracket_color, thickness)
        cv2.line(out, (x2, y2), (x2, y2 - corner_len), bracket_color, thickness)

        # Horizontal scan line sweeping across face
        scan_phase = (t * 1.5) % 1.0
        scan_y = int(y1 + scan_phase * fh)
        overlay = out.copy()
        cv2.line(overlay, (x1, scan_y), (x2, scan_y), self.GREEN, 1)
        cv2.addWeighted(overlay, 0.6, out, 0.4, 0, out)

        # Centre crosshair (small)
        gap = 8
        cv2.line(out, (cx_i - 15, cy_i), (cx_i - gap, cy_i), self.GREEN, 1)
        cv2.line(out, (cx_i + gap, cy_i), (cx_i + 15, cy_i), self.GREEN, 1)
        cv2.line(out, (cx_i, cy_i - 15), (cx_i, cy_i - gap), self.GREEN, 1)
        cv2.line(out, (cx_i, cy_i + gap), (cx_i, cy_i + 15), self.GREEN, 1)

        # Status labels (biometric HUD style)
        status = "LOCKED" if stable else "TRACKING"
        status_color = self.GREEN if stable else self.YELLOW
        cv2.putText(out, f"FACE {status}", (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, status_color, 2)

        # Data readout below face box
        data_y = y2 + 20
        cv2.putText(out, f"POS  [{result.x_robot_mm:.0f}, {result.y_robot_mm:.0f}]",
                    (x1, data_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.GREEN, 1)
        cv2.putText(out, f"SIZE {result.pixel_size:.0f}px",
                    (x1, data_y + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.GREEN, 1)
        if result.z_cam_mm > 0:
            cv2.putText(out, f"DIST {result.z_cam_mm:.0f}mm",
                        (x1, data_y + 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.CYAN, 1)

        if result.in_workspace:
            cv2.putText(out, "IN WORKSPACE",
                        (x1, data_y + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.GREEN, 1)
        else:
            cv2.putText(out, "OUT OF RANGE",
                        (x1, data_y + 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.RED, 1)

        if e6pos:
            cv2.putText(out, e6pos, (10, out.shape[0] - 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.GREEN, 1)

    # ── Shared telemetry block ───────────────────────────────────

    def _draw_telemetry(self, out, result, stable, e6pos):
        lines = [
            f"Camera  (mm): {result.x_cam_mm:.1f}, {result.y_cam_mm:.1f}, {result.z_cam_mm:.1f}",
            f"Robot   (mm): {result.x_robot_mm:.1f}, {result.y_robot_mm:.1f}, {result.z_robot_mm:.1f}",
            f"Angle  (deg): {result.angle_deg:.1f}",
            f"Workspace   : {'OK' if result.in_workspace else 'OUT'}",
            f"Stable      : {'YES' if stable else '...waiting'}",
        ]
        for i, line in enumerate(lines):
            cv2.putText(out, line, (10, 100 + i * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.WHITE, 1)

        if e6pos:
            cv2.putText(out, e6pos, (10, 100 + len(lines) * 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.GREEN, 1)


# ══════════════════════════════════════════════════════════════════
#  HSV TUNER
# ══════════════════════════════════════════════════════════════════

class HSVTuner:
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
            ("H_lo",  8, 179), ("S_lo", 100, 255), ("V_lo", 100, 255),
            ("H_hi", 35, 179), ("S_hi", 255, 255), ("V_hi", 255, 255),
        ]:
            cv2.createTrackbar(name, self.WINDOW, default, max_val, lambda _: None)

        print("HSV Tuner  |  S = save  |  Q = quit")
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
            mask = cv2.inRange(hsv,
                               np.array([h_lo, s_lo, v_lo]),
                               np.array([h_hi, s_hi, v_hi]))
            cv2.imshow(self.WINDOW, cv2.bitwise_and(frame, frame, mask=mask))

            key = cv2.waitKey(1) & 0xFF
            if key == ord("s"):
                cfg = ColorConfig(lower_h=h_lo, lower_s=s_lo, lower_v=v_lo,
                                  upper_h=h_hi, upper_s=s_hi, upper_v=v_hi)
                cfg.to_json(self.output_path)
                print(f"Saved to {self.output_path}")
            elif key == ord("q"):
                break

        cap.release()
        cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════
#  CAMERA MANAGER
# ══════════════════════════════════════════════════════════════════

class CameraManager:
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
            print(f"Available cameras: {cams}")
            idx = cfg.index if cfg.index in cams else cams[0]
        else:
            idx = cfg.index
        self.cap = cv2.VideoCapture(idx, cfg.backend)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera index: {idx}")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  cfg.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        print(f"Opened camera {idx}  ({cfg.width}x{cfg.height})")
        return self.cap

    def release(self):
        if self.cap:
            self.cap.release()


# ══════════════════════════════════════════════════════════════════
#  TERMINAL CONFIRMATION HELPER
# ══════════════════════════════════════════════════════════════════

class TerminalConfirm:
    def __init__(self):
        self._result: Optional[str] = None
        self._thread: Optional[threading.Thread] = None

    def ask(self, prompt: str):
        self._result = None
        print()
        print("=" * 56)
        print(f"  {prompt}")
        print("  " + "-" * 45)
        print("    [Enter]   -> Execute motion")
        print("    s + Enter -> Skip (re-detect)")
        print("    q + Enter -> Quit pipeline")
        print("=" * 56)
        sys.stdout.flush()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        try:
            line = input("  >> ").strip().lower()
            if line == "q":
                self._result = "quit"
            elif line == "s":
                self._result = "no"
            else:
                self._result = "yes"
        except EOFError:
            self._result = "quit"

    def poll(self) -> Optional[str]:
        return self._result


# ══════════════════════════════════════════════════════════════════
#  VISION PIPELINE — top-level orchestrator
# ══════════════════════════════════════════════════════════════════

class VisionPipeline:
    """
    Startup order
    -------------
    1.  Operator starts KRL server program on the robot
    2.  PC connects to robot via EkiManager (TCP client)
    3.  Pipeline begins: HOME → detect → confirm → pick & place → repeat
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
        self.robot_cfg  = robot_cfg
        self.send_robot = send_robot

        # Vision
        self.cam_mgr     = CameraManager(cam_cfg)
        self.detector    = CubeDetector(color_cfg)
        self.transformer = CoordinateTransformer(cam_cfg, robot_cfg, cube_size_m)
        self.tracker     = KalmanTracker()
        self.guard       = StabilityGuard(*stability)
        self.renderer    = OverlayRenderer()

        # Robot
        self.eki   = EkiManager()
        self.robot = RobotController(robot_cfg, self.eki)

        # Logger
        self.logger: Optional[DetectionLogger] = None
        if log_path:
            self.logger = DetectionLogger(log_path)

    def _connect_robot(self) -> bool:
        if not self.send_robot:
            print("DRY-RUN mode — robot not connected")
            return True
        try:
            self.eki.connect(self.robot_cfg.tcp_ip, self.robot_cfg.tcp_port)
            print(f"Connected to robot at {self.robot_cfg.tcp_ip}:{self.robot_cfg.tcp_port}")
            return True
        except Exception as exc:
            print(f"Connection failed: {exc}")
            return False

    # ── Main loop ─────────────────────────────────────────────────

    def run(self):
        if not self._connect_robot():
            print("Robot connection failed. Exiting.")
            return

        cap = self.cam_mgr.open()
        if self.logger:
            self.logger.open()

        print("Pipeline running  |  Q (in OpenCV window) = quit")

        try:
            while True:

                # ── 1. Go HOME ───────────────────────────────────
                if self.send_robot:
                    print("\nMoving to HOME...")
                    if not self.robot.go_home():
                        print("Home move failed.")
                        break

                # ── 2. Detect cube ───────────────────────────────
                print("Waiting for stable cube detection...")
                detection = self._wait_for_stable_detection(cap)

                if detection is None:
                    break

                e6pos = self.transformer.to_e6pos(detection)
                print(f"Stable cube detected at: {e6pos}")

                if self.logger:
                    self.logger.log(detection)

                # ── 3. Confirm before motion ─────────────────────
                decision = self._confirm_with_live_view(cap, detection, e6pos)

                if decision == "quit":
                    print("Quit requested.")
                    break
                elif decision == "no":
                    print("Skipped — re-detecting...")
                    continue

                print("Confirmed — executing motion")

                # ── 4. Pick & place ──────────────────────────────
                if self.send_robot:
                    success = self.robot.execute_pick_and_place(detection)
                    if not success:
                        print("Sequence failed — retrying from HOME")
                else:
                    print(f"[DRY-RUN] execute_pick_and_place({e6pos})")
                    time.sleep(2.0)

        finally:
            self.cam_mgr.release()
            cv2.destroyAllWindows()
            if self.logger:
                self.logger.close()
            if self.send_robot:
                self.eki.close()
            print("Pipeline stopped.")

    # ── Detection loop ────────────────────────────────────────────

    def _wait_for_stable_detection(
        self, cap: cv2.VideoCapture
    ) -> Optional[DetectionResult]:
        self.tracker.reset()
        self.guard.reset()

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Frame grab failed")
                return None

            result, mask = self.detector.detect_with_mask(frame)
            e6pos  = None
            stable = False

            if result is not None:
                result.cx_px, result.cy_px = self.tracker.update(
                    result.cx_px, result.cy_px
                )
                fh, fw = frame.shape[:2]
                result = self.transformer.transform(result, fw, fh)
                if result is not None and result.in_workspace:
                    e6pos  = self.transformer.to_e6pos(result)
                    stable = self.guard.is_stable(result)
                    if stable:
                        return result
            else:
                self.tracker.reset()
                self.guard.reset()

            vis = self.renderer.draw(
                frame, result, stable, e6pos, self.robot.state
            )
            cv2.imshow("Vision -> KUKA", vis)
            cv2.imshow("Mask",           mask)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                return None

    # ── Confirmation with live camera feed ────────────────────────

    def _confirm_with_live_view(
        self,
        cap:       cv2.VideoCapture,
        detection: DetectionResult,
        e6pos:     str,
    ) -> str:
        tc = TerminalConfirm()
        tc.ask(f"Move robot to {e6pos} ?")

        while True:
            ret, frame = cap.read()
            if ret:
                result, mask = self.detector.detect_with_mask(frame)
                if result is not None:
                    result.cx_px, result.cy_px = self.tracker.update(
                        result.cx_px, result.cy_px
                    )
                    fh, fw = frame.shape[:2]
                    result = self.transformer.transform(result, fw, fh)

                vis = self.renderer.draw(
                    frame, result, True, e6pos,
                    self.robot.state, awaiting_confirm=True,
                )
                cv2.imshow("Vision -> KUKA", vis)
                cv2.imshow("Mask", mask)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                return "quit"

            answer = tc.poll()
            if answer is not None:
                return answer


# ══════════════════════════════════════════════════════════════════
#  DARK THEME PALETTE (from test_eki_motion)
# ══════════════════════════════════════════════════════════════════
BG  = "#000000"    # pure black main background
BG2 = "#0a0a0a"    # near-black panel background
BG3 = "#141414"    # input field background
FG  = "#e0e0e0"    # clean white primary text
FG2 = "#555555"    # muted secondary text
GRN = "#4a9e6a"    # muted success green
RED = "#c44455"    # muted error red
ORG = "#ff6600"    # KUKA brand orange — primary accent
YEL = "#aa8833"    # muted warm yellow
CYN = "#6699aa"    # muted steel blue
FNT = "Segoe UI"   # UI font
MNO = "Consolas"   # monospace font

# Modern styling tokens
BRD     = "#1a1a1a"   # subtle border / separator
ORG_DIM = "#3d2200"   # dim orange (pulse low)
ORG_MID = "#7f3300"   # mid orange (hover / pulse mid)
BTN_BG  = "#111111"   # standard button background
BTN_HOV = "#1a1a1a"   # button hover background


# ══════════════════════════════════════════════════════════════════
#  VISION GUI — Tkinter control panel (dark theme)
# ══════════════════════════════════════════════════════════════════

class VisionGUI:

    FEED_WIDTH  = 480
    FEED_HEIGHT = 220

    STATE_COLORS = {
        RobotState.IDLE:        (GRN,  "#FFFFFF"),
        RobotState.HOMING:      (ORG,  "#FFFFFF"),
        RobotState.DETECTING:   (CYN,  "#FFFFFF"),
        RobotState.APPROACHING: (ORG,  "#FFFFFF"),
        RobotState.PICKING:     (ORG,  "#FFFFFF"),
        RobotState.LIFTING:     (ORG,  "#FFFFFF"),
        RobotState.PLACING:     (ORG,  "#FFFFFF"),
        RobotState.RETURNING:   (ORG,  "#FFFFFF"),
        RobotState.ERROR:       (RED,  "#FFFFFF"),
    }

    def __init__(self, color_cfg: ColorConfig, robot_cfg: RobotConfig = None):
        self.root = tk.Tk()
        self.root.title("KUKA Vision Control Panel")
        self.root.configure(bg=BG)
        self.root.resizable(True, True)
        self.root.maxsize(1280, 900)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._running = True
        self._user_action: Optional[str] = None
        self._color_cfg = color_cfg
        self._robot_cfg = robot_cfg or RobotConfig()

        # Pulse animation state
        self._pulse_active = False
        self._pulse_after_id = None
        self._pulse_step = 0
        self._pulse_ascending = True

        self._photo_feed: Optional[ImageTk.PhotoImage] = None
        self._photo_mask: Optional[ImageTk.PhotoImage] = None

        # ttk dark style for Combobox
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=BG3, background=BG2,
                        foreground=FG, arrowcolor=ORG,
                        selectbackground=ORG, selectforeground="white")
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG3)],
                  foreground=[("readonly", FG)])

        self._build_ui()

        # Grid weights for resizable layout (3-row layout)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=0)   # top: video + XY plane
        self.root.rowconfigure(1, weight=0)   # middle: status + HSV + jog + capture
        self.root.rowconfigure(2, weight=1, minsize=200)  # terminal (expands, min 200px)

    # ── UI construction ───────────────────────────────────────────

    def _build_ui(self):
        self._build_top_row()              # row 0: video feeds + XY plane
        self._build_middle_row()           # row 1: status+connect, HSV, jog, capture
        self._build_terminal()             # row 2: raw packet terminal

    # ── Modern styling helpers ─────────────────────────────────

    @staticmethod
    def _lighten(hex_color, amount=25):
        """Lighten a hex color by an integer amount per channel."""
        h = hex_color.lstrip("#")
        r = min(255, int(h[0:2], 16) + amount)
        g = min(255, int(h[2:4], 16) + amount)
        b = min(255, int(h[4:6], 16) + amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _lerp_color(hex_a, hex_b, t):
        """Linearly interpolate between two hex colors. t in [0, 1]."""
        a = hex_a.lstrip("#")
        b = hex_b.lstrip("#")
        r = int(int(a[0:2], 16) * (1 - t) + int(b[0:2], 16) * t)
        g = int(int(a[2:4], 16) * (1 - t) + int(b[2:4], 16) * t)
        bv = int(int(a[4:6], 16) * (1 - t) + int(b[4:6], 16) * t)
        return f"#{r:02x}{g:02x}{bv:02x}"

    def _apply_hover(self, button, bg_normal, bg_hover):
        """Bind Enter/Leave events for hover color transitions."""
        def on_enter(e):
            if str(button.cget("state")) != "disabled":
                button.config(bg=bg_hover)
        def on_leave(e):
            if str(button.cget("state")) != "disabled":
                button.config(bg=bg_normal)
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)

    def _make_button(self, parent, text, bg, fg="white", command=None,
                     font=None, **kwargs):
        """Create a styled flat button with hover effect."""
        font = font or (FNT, 10, "bold")
        hover_bg = self._lighten(bg, 25)
        btn = tk.Button(
            parent, text=text, font=font,
            bg=bg, fg=fg, activebackground=hover_bg, activeforeground=fg,
            relief=tk.FLAT, bd=0, padx=12, pady=4,
            cursor="hand2", command=command, **kwargs,
        )
        self._apply_hover(btn, bg, hover_bg)
        return btn

    def _panel(self, parent, title, title_color=ORG):
        """Create a modern panel: Frame with header label and 1px border."""
        outer = tk.Frame(parent, bg=BRD, bd=0)
        inner = tk.Frame(outer, bg=BG2, bd=0)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        header = tk.Label(inner, text=title.upper(), bg=BG2, fg=title_color,
                          font=(FNT, 8, "bold"), anchor="w", padx=8, pady=4)
        header.pack(fill=tk.X)

        sep = tk.Frame(inner, bg=BRD, height=1)
        sep.pack(fill=tk.X, padx=8)

        content = tk.Frame(inner, bg=BG2)
        content.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        return outer, content

    # ── XY plane helpers ───────────────────────────────────────

    def _draw_xy_grid(self):
        """Draw the workspace grid on the XY canvas."""
        c = self._xy_canvas
        sz = self._xy_canvas_size
        c.delete("grid")

        wx = self._robot_cfg.workspace_x
        wy = self._robot_cfg.workspace_y
        margin = 20

        # Map workspace mm → canvas px
        def mm_to_px(x_mm, y_mm):
            px = margin + (x_mm - wx[0]) / (wx[1] - wx[0]) * (sz - 2 * margin)
            py = (sz - margin) - (y_mm - wy[0]) / (wy[1] - wy[0]) * (sz - 2 * margin)
            return px, py

        # Workspace rectangle
        x0, y0 = mm_to_px(wx[0], wy[0])
        x1, y1 = mm_to_px(wx[1], wy[1])
        c.create_rectangle(x0, y1, x1, y0, outline=BRD, width=1, tags="grid")

        # 100mm grid lines
        step = 100
        x_start = int(wx[0] / step) * step
        y_start = int(wy[0] / step) * step
        for x_mm in range(x_start, int(wx[1]) + 1, step):
            if wx[0] <= x_mm <= wx[1]:
                px, _ = mm_to_px(x_mm, 0)
                c.create_line(px, y1, px, y0, fill=BRD, tags="grid")
                c.create_text(px, y0 + 10, text=str(int(x_mm)),
                              fill=FG2, font=(MNO, 7), tags="grid")
        for y_mm in range(y_start, int(wy[1]) + 1, step):
            if wy[0] <= y_mm <= wy[1]:
                _, py = mm_to_px(0, y_mm)
                c.create_line(x0, py, x1, py, fill=BRD, tags="grid")
                c.create_text(x0 - 12, py, text=str(int(y_mm)),
                              fill=FG2, font=(MNO, 7), tags="grid")

        # Axis labels
        c.create_text(sz // 2, sz - 4, text="X (mm) →", fill=FG2,
                       font=(FNT, 8), tags="grid")
        c.create_text(6, sz // 2, text="Y", fill=FG2,
                       font=(FNT, 8), angle=90, tags="grid")

        self._xy_mm_to_px = mm_to_px

    def update_xy_plane(self, result: Optional[DetectionResult]):
        """Plot the cube position on the XY canvas."""
        c = self._xy_canvas
        c.delete("cube")
        if result is None or not result.in_workspace:
            return
        try:
            px, py = self._xy_mm_to_px(result.x_robot_mm, result.y_robot_mm)
            r = 6
            c.create_oval(px - r, py - r, px + r, py + r,
                          fill=ORG, outline="white", width=1, tags="cube")
            c.create_text(px + 12, py - 10,
                          text=f"({result.x_robot_mm:.0f}, {result.y_robot_mm:.0f})",
                          fill=ORG, font=(MNO, 8), anchor="w", tags="cube")
        except Exception:
            pass

    # ── UI panel builders ──────────────────────────────────────

    def _build_top_row(self):
        """Row 0: Camera feeds (left) + XY plane canvas (right)."""
        top = tk.Frame(self.root, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(4, 0))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=0)

        # ── Left: video feeds ──
        vid_frame = tk.Frame(top, bg=BG)
        vid_frame.grid(row=0, column=0, sticky="nw")

        self.lbl_feed = tk.Label(vid_frame, bg="black",
                                 width=self.FEED_WIDTH, height=self.FEED_HEIGHT)
        self.lbl_feed.grid(row=0, column=0, padx=(0, 3))

        self.lbl_mask = tk.Label(vid_frame, bg="black",
                                 width=self.FEED_WIDTH, height=self.FEED_HEIGHT)
        self.lbl_mask.grid(row=0, column=1, padx=(3, 0))

        tk.Label(vid_frame, text="VISION FEED", bg=BG, fg=FG2,
                 font=(FNT, 8, "bold")).grid(row=1, column=0, pady=(2, 0))
        tk.Label(vid_frame, text="HSV MASK", bg=BG, fg=FG2,
                 font=(FNT, 8, "bold")).grid(row=1, column=1, pady=(2, 0))

        # ── Right: XY plane canvas ──
        xy_outer, xy_content = self._panel(top, "XY Plane (Robot Base)", CYN)
        xy_outer.grid(row=0, column=1, sticky="ns", padx=(6, 0))

        self._xy_canvas_size = 300
        self._xy_canvas = tk.Canvas(
            xy_content, width=self._xy_canvas_size,
            height=self._xy_canvas_size,
            bg="#050505", highlightthickness=0)
        self._xy_canvas.pack(padx=4, pady=4)
        self._draw_xy_grid()

    def _build_middle_row(self):
        """Row 1: Status+Connect | HSV Tuner | Jog | Capture — 4 columns."""
        mid = tk.Frame(self.root, bg=BG)
        mid.grid(row=1, column=0, sticky="ew", padx=8, pady=4)
        for i in range(4):
            mid.columnconfigure(i, weight=1)

        self.buttons = {}

        # ═══════════════════════════════════════════════════════════
        #  COL 0 — Status & Connection
        # ═══════════════════════════════════════════════════════════
        outer0, c0 = self._panel(mid, "Connection")
        outer0.grid(row=0, column=0, sticky="nsew", padx=(0, 3))

        # Detection mode selector
        det_frame = tk.Frame(c0, bg=BG2)
        det_frame.pack(fill=tk.X, padx=4, pady=(2, 4))
        tk.Label(det_frame, text="Detect:", bg=BG2, fg=FG2,
                 font=(MNO, 8, "bold")).pack(side=tk.LEFT, padx=(0, 4))
        self.var_detect_mode = tk.StringVar(value="Orange Cube")
        self._detect_combo = ttk.Combobox(
            det_frame, textvariable=self.var_detect_mode,
            values=list(DETECTOR_PRESETS.keys()),
            state="readonly", width=14, font=(MNO, 9))
        self._detect_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._detect_combo.bind("<<ComboboxSelected>>",
                                lambda e: self._on_button("detect_mode"))

        # Status indicators
        status_bar = tk.Frame(c0, bg=BG2)
        status_bar.pack(fill=tk.X, pady=(2, 4))

        self.lbl_fps = tk.Label(status_bar, text="FPS: --", bg=BG2, fg=FG2,
                                font=(MNO, 9), width=10)
        self.lbl_fps.pack(side=tk.LEFT, padx=2)

        self.lbl_z_dist = tk.Label(status_bar, text="Z: -- mm", bg=BG2, fg=ORG,
                                   font=(MNO, 9), width=12)
        self.lbl_z_dist.pack(side=tk.LEFT, padx=2)

        self.lbl_connection = tk.Label(status_bar, text="\u2b24 Disconnected",
                                       bg=BG2, font=(MNO, 9), fg=RED)
        self.lbl_connection.pack(side=tk.LEFT, padx=2)

        self.lbl_robot_state = tk.Label(c0, text="Robot: IDLE",
                                        font=(MNO, 9, "bold"),
                                        bg=GRN, fg="white", relief=tk.FLAT)
        self.lbl_robot_state.pack(fill=tk.X, padx=4, pady=2)

        self.lbl_pipeline = tk.Label(c0, text="Pipeline: IDLE",
                                     bg=BG2, fg=FG2, font=(MNO, 9))
        self.lbl_pipeline.pack(fill=tk.X, padx=4)

        # IP / Port
        conn_frame = tk.Frame(c0, bg=BG2)
        conn_frame.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(conn_frame, text="IP:", bg=BG2, fg=FG2,
                 font=(FNT, 8)).grid(row=0, column=0, sticky="e", padx=(0, 2))
        self.var_ip = tk.StringVar(value=self._robot_cfg.tcp_ip)
        tk.Entry(conn_frame, textvariable=self.var_ip, font=(MNO, 9),
                 width=13, bg=BG3, fg=FG, insertbackground=ORG,
                 relief=tk.FLAT, justify="center").grid(row=0, column=1)
        tk.Label(conn_frame, text="Port:", bg=BG2, fg=FG2,
                 font=(FNT, 8)).grid(row=1, column=0, sticky="e", padx=(0, 2))
        self.var_port = tk.StringVar(value=str(self._robot_cfg.tcp_port))
        tk.Entry(conn_frame, textvariable=self.var_port, font=(MNO, 9),
                 width=13, bg=BG3, fg=FG, insertbackground=ORG,
                 relief=tk.FLAT, justify="center").grid(row=1, column=1, pady=2)

        # Connect / Disconnect
        conn_btns = tk.Frame(c0, bg=BG2)
        conn_btns.pack(fill=tk.X, padx=4, pady=2)
        btn_conn = self._make_button(conn_btns, "Connect", bg=GRN,
                                     font=(FNT, 9, "bold"),
                                     command=lambda: self._on_button("connect"))
        btn_conn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 2))
        self.buttons["connect"] = btn_conn
        btn_disc = self._make_button(conn_btns, "Disconnect", bg=RED,
                                     font=(FNT, 9, "bold"),
                                     command=lambda: self._on_button("disconnect"))
        btn_disc.config(state=tk.DISABLED)
        btn_disc.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(2, 0))
        self.buttons["disconnect"] = btn_disc

        # ── Speed control ──
        spd_frame = tk.Frame(c0, bg=BG2)
        spd_frame.pack(fill=tk.X, padx=4, pady=(4, 2))

        tk.Label(spd_frame, text="Speed (m/s):", bg=BG2, fg=FG2,
                 font=(MNO, 8)).pack(side=tk.LEFT, padx=(0, 2))
        self.var_speed = tk.DoubleVar(value=0.2)
        self._speed_label = tk.Label(spd_frame, text="0.20", bg=BG2,
                                     fg=ORG, font=(MNO, 9, "bold"), width=5)
        self._speed_label.pack(side=tk.RIGHT, padx=(2, 0))
        self._speed_scale = tk.Scale(
            c0, variable=self.var_speed, from_=0.01, to=2.0,
            resolution=0.01, orient=tk.HORIZONTAL,
            bg=BG2, fg=FG, troughcolor=BG3, highlightthickness=0,
            activebackground=ORG, sliderrelief=tk.FLAT, showvalue=False,
            command=self._on_speed_change)
        self._speed_scale.pack(fill=tk.X, padx=4, pady=(0, 2))

        self.btn_send_speed = self._make_button(
            c0, "Set Speed", bg=BTN_BG, fg=FG2,
            font=(FNT, 8, "bold"),
            command=lambda: self._on_button("set_speed"))
        self.btn_send_speed.config(state=tk.DISABLED)
        self.btn_send_speed.pack(fill=tk.X, padx=4, pady=(0, 2))
        self.buttons["set_speed"] = self.btn_send_speed

        # E-STOP + Quit
        btn_estop = self._make_button(c0, "EMERGENCY STOP", bg="#881122",
                                      command=lambda: self._on_button("estop"))
        btn_estop.pack(fill=tk.X, padx=4, pady=(4, 2))
        self.buttons["estop"] = btn_estop
        btn_quit = self._make_button(c0, "Quit", bg=BTN_BG, fg=FG2,
                                     font=(FNT, 9, "bold"),
                                     command=lambda: self._on_button("quit"))
        btn_quit.pack(fill=tk.X, padx=4, pady=(0, 4))
        self.buttons["quit"] = btn_quit

        # ═══════════════════════════════════════════════════════════
        #  COL 1 — HSV Tuner
        # ═══════════════════════════════════════════════════════════
        outer1, c1 = self._panel(mid, "HSV Color Tuner")
        outer1.grid(row=0, column=1, sticky="nsew", padx=3)

        self.hsv_vars = {}
        slider_defs = [
            ("H Lo", "lower_h", 0, 179), ("S Lo", "lower_s", 0, 255),
            ("V Lo", "lower_v", 0, 255), ("H Hi", "upper_h", 0, 179),
            ("S Hi", "upper_s", 0, 255), ("V Hi", "upper_v", 0, 255),
        ]
        for i, (label, attr, from_, to_) in enumerate(slider_defs):
            tk.Label(c1, text=label, bg=BG2, fg=FG2,
                     font=(MNO, 8)).grid(row=i, column=0, sticky="w", padx=2)
            var = tk.IntVar(value=getattr(self._color_cfg, attr))
            scale = tk.Scale(
                c1, variable=var, from_=from_, to=to_,
                orient=tk.HORIZONTAL, length=120,
                bg=BG2, fg=FG, troughcolor=BG3, highlightthickness=0,
                activebackground=ORG, sliderrelief=tk.FLAT,
                command=lambda val, a=attr: self._on_hsv_change(a, int(val)))
            scale.grid(row=i, column=1, padx=2, pady=0)
            self.hsv_vars[attr] = var
        btn_save = self._make_button(c1, "Save HSV", bg=BTN_BG, fg=FG,
                                     font=(FNT, 8, "bold"),
                                     command=self._on_save_hsv)
        btn_save.grid(row=len(slider_defs), column=0, columnspan=2, pady=4)

        # ═══════════════════════════════════════════════════════════
        #  COL 2 — Jog (Go To Frame)
        # ═══════════════════════════════════════════════════════════
        outer2, c2 = self._panel(mid, "Jog — Go To Frame")
        outer2.grid(row=0, column=2, sticky="nsew", padx=3)

        field_frame = tk.Frame(c2, bg=BG2)
        field_frame.pack(fill=tk.X)
        self.jog_vars = {}
        axes = ["X", "Y", "Z", "A", "B", "C"]
        for idx, axis in enumerate(axes):
            r, c = divmod(idx, 3)
            cell = tk.Frame(field_frame, bg=BG2)
            cell.grid(row=r, column=c, padx=3, pady=2, sticky="ew")
            field_frame.columnconfigure(c, weight=1)
            tk.Label(cell, text=f"{axis}:", bg=BG2, fg=FG2,
                     font=(MNO, 9, "bold")).pack(side=tk.LEFT)
            var = tk.StringVar(value="0")
            tk.Entry(cell, textvariable=var, font=(MNO, 9), width=7,
                     bg=BG3, fg=FG, insertbackground=ORG,
                     relief=tk.FLAT, justify="right").pack(
                         side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
            self.jog_vars[axis.lower()] = var

        self.btn_jog = self._make_button(c2, "MOVE TO FRAME", bg=GRN,
                                         command=lambda: self._on_button("jog"))
        self.btn_jog.config(state=tk.DISABLED)
        self.btn_jog.pack(fill=tk.X, pady=(4, 1), ipady=2)

        self.btn_read_pos = self._make_button(
            c2, "Read Current Pos", bg=BTN_BG, fg=FG2,
            font=(FNT, 8, "bold"),
            command=lambda: self._on_button("read_pos"))
        self.btn_read_pos.config(state=tk.DISABLED)
        self.btn_read_pos.pack(fill=tk.X, pady=(0, 2), ipady=1)

        self.btn_follow = self._make_button(
            c2, "FOLLOW CUBE", bg="#005588",
            font=(FNT, 9, "bold"),
            command=lambda: self._on_button("follow"))
        self.btn_follow.config(state=tk.DISABLED)
        self.btn_follow.pack(fill=tk.X, pady=(0, 4), ipady=2)
        self.buttons["follow"] = self.btn_follow
        self._follow_active = False

        # ═══════════════════════════════════════════════════════════
        #  COL 3 — Capture & Confirm
        # ═══════════════════════════════════════════════════════════
        outer3, c3 = self._panel(mid, "Capture & Confirm")
        outer3.grid(row=0, column=3, sticky="nsew", padx=(3, 0))

        # Capture button (always available in IDLE phase)
        btn_capture = self._make_button(
            c3, "Capture Target", bg=ORG,
            command=lambda: self._on_button("capture"))
        btn_capture.pack(fill=tk.X, padx=4, pady=(2, 4))
        self.buttons["capture"] = btn_capture

        # TARGET LOCKED indicator
        self._tgt_frame = tk.Frame(c3, bg=BG2)
        self._tgt_frame.pack(fill=tk.BOTH, expand=True)

        self._tgt_lock_label = tk.Label(
            self._tgt_frame, text="", bg=BG2, fg=ORG,
            font=(FNT, 9, "bold"))
        self._tgt_lock_label.pack(anchor="w", padx=4, pady=(0, 2))

        tgt_field = tk.Frame(self._tgt_frame, bg=BG2)
        tgt_field.pack(fill=tk.X)
        self._tgt_vars = {}
        self._tgt_entries = []
        for idx, axis in enumerate(axes):
            r, c = divmod(idx, 3)
            cell = tk.Frame(tgt_field, bg=BG2)
            cell.grid(row=r, column=c, padx=3, pady=1, sticky="ew")
            tgt_field.columnconfigure(c, weight=1)
            tk.Label(cell, text=f"{axis}:", bg=BG2, fg=FG2,
                     font=(MNO, 8, "bold")).pack(side=tk.LEFT)
            var = tk.StringVar(value="--")
            ent = tk.Entry(cell, textvariable=var, font=(MNO, 8), width=7,
                           bg=BG3, fg=ORG, insertbackground=ORG,
                           relief=tk.FLAT, justify="right",
                           state=tk.DISABLED)
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
            self._tgt_vars[axis.lower()] = var
            self._tgt_entries.append(ent)

        btn_confirm = self._make_button(
            self._tgt_frame, "CONFIRM & SEND", bg=ORG,
            command=lambda: self._on_button("confirm"))
        btn_confirm.config(state=tk.DISABLED)
        btn_confirm.pack(fill=tk.X, padx=4, pady=(4, 1), ipady=2)
        self.buttons["confirm"] = btn_confirm

        btn_skip = self._make_button(
            self._tgt_frame, "SKIP", bg=BTN_BG, font=(FNT, 8, "bold"),
            command=lambda: self._on_button("skip"))
        btn_skip.config(state=tk.DISABLED)
        btn_skip.pack(fill=tk.X, padx=4, pady=(0, 4), ipady=1)
        self.buttons["skip"] = btn_skip

    def _build_terminal(self):
        """Row 2: Split terminal — Packets (left) + Errors (right)."""
        frame = tk.Frame(self.root, bg=BG)
        frame.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 5))
        frame.columnconfigure(0, weight=3)
        frame.columnconfigure(1, weight=2)
        frame.rowconfigure(0, weight=1)

        # ── Left: Packets terminal ──
        pkt_outer, pkt_content = self._panel(frame, "Packets (TX / RX)")
        pkt_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 3))

        pkt_frame = tk.Frame(pkt_content, bg=BG)
        pkt_frame.pack(fill=tk.BOTH, expand=True)

        self._terminal_text = tk.Text(
            pkt_frame, height=10, bg="#050505", fg=GRN,
            font=(MNO, 10), relief=tk.FLAT, insertbackground=GRN,
            wrap=tk.WORD, state=tk.DISABLED)
        self._terminal_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb1 = tk.Scrollbar(pkt_frame, command=self._terminal_text.yview,
                           bg=BG2, troughcolor=BG)
        sb1.pack(side=tk.RIGHT, fill=tk.Y)
        self._terminal_text.config(yscrollcommand=sb1.set)

        self._terminal_text.tag_configure("tx", foreground=CYN)
        self._terminal_text.tag_configure("rx", foreground=GRN)
        self._terminal_text.tag_configure("sys", foreground=FG2)

        # ── Right: Error log ──
        err_outer, err_content = self._panel(frame, "Errors", RED)
        err_outer.grid(row=0, column=1, sticky="nsew", padx=(3, 0))

        err_frame = tk.Frame(err_content, bg=BG)
        err_frame.pack(fill=tk.BOTH, expand=True)

        self._error_text = tk.Text(
            err_frame, height=10, bg="#0a0000", fg=RED,
            font=(MNO, 10), relief=tk.FLAT, insertbackground=RED,
            wrap=tk.WORD, state=tk.DISABLED)
        self._error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sb2 = tk.Scrollbar(err_frame, command=self._error_text.yview,
                           bg=BG2, troughcolor=BG)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._error_text.config(yscrollcommand=sb2.set)

        self._error_text.tag_configure("code", foreground=ORG,
                                       font=(MNO, 10, "bold"))
        self._error_text.tag_configure("msg", foreground=RED)
        self._error_text.tag_configure("trace", foreground="#884444")

        self._error_counter = 0

    # ── Jog / connection helpers ───────────────────────────────────

    def get_jog_frame(self) -> Optional[list]:
        axes = ["x", "y", "z", "a", "b", "c"]
        values = []
        for axis in axes:
            try:
                values.append(float(self.jog_vars[axis].get()))
            except ValueError:
                self.log(f"Jog error: invalid value for {axis.upper()}")
                return None
        return values

    def set_jog_frame(self, x, y, z, a, b, c):
        for axis, val in zip(["x", "y", "z", "a", "b", "c"],
                             [x, y, z, a, b, c]):
            self.jog_vars[axis].set(f"{float(val):.2f}")

    def get_connection_info(self) -> tuple:
        ip = self.var_ip.get().strip()
        try:
            port = int(self.var_port.get().strip())
        except ValueError:
            self.log("Connection error: invalid port number")
            return None, None
        return ip, port

    def set_jog_enabled(self, enabled: bool):
        st = tk.NORMAL if enabled else tk.DISABLED
        self.btn_jog.config(state=st)
        self.btn_read_pos.config(state=st)
        # Follow button enabled when connected (regardless of busy state)
        if not self._follow_active:
            self.btn_follow.config(state=tk.NORMAL if enabled else tk.DISABLED)

    def set_follow_active(self, active: bool):
        """Toggle follow button appearance."""
        self._follow_active = active
        if active:
            self.btn_follow.config(text="STOP FOLLOW", bg=RED)
        else:
            self.btn_follow.config(text="FOLLOW CUBE", bg="#005588")

    def set_connected_buttons(self, connected: bool):
        """Enable/disable buttons that require connection."""
        st = tk.NORMAL if connected else tk.DISABLED
        self.buttons["disconnect"].config(state=st)
        self.buttons["connect"].config(
            state=tk.DISABLED if connected else tk.NORMAL)
        self.btn_follow.config(state=st)
        self.btn_send_speed.config(state=st)

    # ── Log / response helpers ─────────────────────────────────────

    def log(self, msg: str):
        """Log a system message to the Packets terminal."""
        ts = time.strftime("%H:%M:%S")
        self._terminal_text.config(state=tk.NORMAL)
        self._terminal_text.insert(tk.END, f"[{ts}] {msg}\n", "sys")
        self._terminal_text.see(tk.END)
        self._terminal_text.config(state=tk.DISABLED)

    def log_packet(self, direction: str, data: str):
        """Log a raw TX/RX packet to the Packets terminal."""
        ts = time.strftime("%H:%M:%S")
        tag = "tx" if direction == "TX" else "rx"
        arrow = "→" if direction == "TX" else "←"
        line = f"[{ts}] {direction} {arrow} {data.strip()}\n"
        self._terminal_text.config(state=tk.NORMAL)
        self._terminal_text.insert(tk.END, line, tag)
        self._terminal_text.see(tk.END)
        self._terminal_text.config(state=tk.DISABLED)

    def log_error(self, code: str, msg: str, trace: str = ""):
        """Log an error with code to the Errors panel for traceback."""
        self._error_counter += 1
        ts = time.strftime("%H:%M:%S")
        self._error_text.config(state=tk.NORMAL)
        self._error_text.insert(tk.END, f"[{ts}] ", "msg")
        self._error_text.insert(tk.END, f"{code}", "code")
        self._error_text.insert(tk.END, f"  {msg}\n", "msg")
        if trace:
            for line in trace.strip().splitlines():
                self._error_text.insert(tk.END, f"  {line}\n", "trace")
        self._error_text.see(tk.END)
        self._error_text.config(state=tk.DISABLED)

    def set_response(self, text: str, success: bool = True):
        """Log a response to the Packets terminal."""
        self.log(f"{'✓' if success else '✗'} {text}")

    def update_target(self, x, y, z, a, b, c):
        """Populate the editable target fields."""
        for axis, val in zip(["x", "y", "z", "a", "b", "c"],
                             [x, y, z, a, b, c]):
            self._tgt_vars[axis].set(f"{val:.1f}")

    def clear_target(self):
        for sv in self._tgt_vars.values():
            sv.set("--")

    def get_target_values(self) -> Optional[list]:
        """Read the 6 target entries, return [x,y,z,a,b,c] or None."""
        values = []
        for axis in ["x", "y", "z", "a", "b", "c"]:
            try:
                values.append(float(self._tgt_vars[axis].get()))
            except ValueError:
                self.log(f"Target error: invalid value for {axis.upper()}")
                return None
        return values

    def set_target_enabled(self, enabled: bool):
        """Enable/disable the target confirmation zone."""
        st = tk.NORMAL if enabled else tk.DISABLED
        for entry in self._tgt_entries:
            entry.config(state=st)
        self.buttons["confirm"].config(state=st)
        self.buttons["skip"].config(state=st)
        if enabled:
            self._tgt_lock_label.config(text="\u25cf  TARGET LOCKED  \u25cf")
        else:
            self._tgt_lock_label.config(text="")
            self._tgt_frame.config(bg=BG2)

    def log_detection(self, msg: str):
        """Log detection info to the terminal."""
        self.log(f"[DET] {msg}")

    # ── Public update methods (called by GUIPipeline) ─────────────

    def update_feed(self, bgr_frame: np.ndarray):
        resized = cv2.resize(bgr_frame, (self.FEED_WIDTH, self.FEED_HEIGHT),
                             interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        self._photo_feed = ImageTk.PhotoImage(image=img)
        self.lbl_feed.config(image=self._photo_feed)

    def update_mask(self, mask: np.ndarray):
        resized = cv2.resize(mask, (self.FEED_WIDTH, self.FEED_HEIGHT),
                             interpolation=cv2.INTER_AREA)
        rgb_mask = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        img = Image.fromarray(rgb_mask)
        self._photo_mask = ImageTk.PhotoImage(image=img)
        self.lbl_mask.config(image=self._photo_mask)

    def update_telemetry(self, result: Optional[DetectionResult],
                         stable: bool, stable_count: int,
                         required_frames: int, e6pos: Optional[str]):
        # Update live Z distance label
        if result is not None and result.z_cam_mm > 0:
            self.lbl_z_dist.config(text=f"Z: {result.z_cam_mm:.0f} mm")
        else:
            self.lbl_z_dist.config(text="Z: -- mm")

    def update_robot_state(self, state: RobotState):
        bg, fg = self.STATE_COLORS.get(state, ("#95A5A6", "#FFFFFF"))
        self.lbl_robot_state.config(text=f"Robot: {state.name}", bg=bg, fg=fg)

    def update_fps(self, fps: float):
        self.lbl_fps.config(text=f"FPS: {fps:.1f}")

    def update_connection(self, connected: bool, dry_run: bool = False):
        if dry_run:
            self.lbl_connection.config(text="  \u2b24 DRY-RUN", fg=YEL)
        elif connected:
            self.lbl_connection.config(text="  \u2b24 Connected", fg=GRN)
        else:
            self.lbl_connection.config(text="  \u2b24 Disconnected", fg=RED)

    def update_pipeline_state(self, text: str):
        self.lbl_pipeline.config(text=f"Pipeline: {text}")

    def set_awaiting_confirm(self, awaiting: bool):
        self.set_target_enabled(awaiting)
        if awaiting:
            self.start_pulse()
        else:
            self.stop_pulse()

    # ── Pulse animation ───────────────────────────────────────

    def start_pulse(self):
        """Start pulsing the target confirmation zone."""
        if self._pulse_active:
            return
        self._pulse_active = True
        self._pulse_step = 0
        self._pulse_ascending = True
        self._pulse_tick()

    def stop_pulse(self):
        """Stop pulsing and reset target frame to default."""
        self._pulse_active = False
        if self._pulse_after_id is not None:
            self.root.after_cancel(self._pulse_after_id)
            self._pulse_after_id = None
        self._tgt_frame.config(bg=BG2)
        self._update_tgt_children_bg(BG2)
        self.buttons["confirm"].config(bg=ORG)

    def _pulse_tick(self):
        """Animate one step of the pulse (~60ms, 16 steps per cycle)."""
        if not self._pulse_active:
            return

        STEPS = 16
        t = self._pulse_step / STEPS
        # smoothstep ease in-out
        t = t * t * (3 - 2 * t)

        # Interpolate frame background
        frame_color = self._lerp_color(ORG_DIM, ORG_MID, t)
        # Interpolate confirm button background
        btn_color = self._lerp_color(ORG_MID, ORG, t)

        self._tgt_frame.config(bg=frame_color)
        self._update_tgt_children_bg(frame_color)
        self.buttons["confirm"].config(bg=btn_color)

        # Advance step
        if self._pulse_ascending:
            self._pulse_step += 1
            if self._pulse_step >= STEPS:
                self._pulse_ascending = False
        else:
            self._pulse_step -= 1
            if self._pulse_step <= 0:
                self._pulse_ascending = True

        self._pulse_after_id = self.root.after(60, self._pulse_tick)

    def _update_tgt_children_bg(self, color):
        """Recursively update bg of children in target frame (skip Entry)."""
        for child in self._tgt_frame.winfo_children():
            try:
                if not isinstance(child, tk.Entry):
                    child.config(bg=color)
                    for grandchild in child.winfo_children():
                        if not isinstance(grandchild, tk.Entry):
                            grandchild.config(bg=color)
            except tk.TclError:
                pass

    def poll_action(self) -> Optional[str]:
        action = self._user_action
        self._user_action = None
        return action

    def is_running(self) -> bool:
        return self._running

    # ── Callbacks ─────────────────────────────────────────────────

    def _on_button(self, action: str):
        self._user_action = action

    def _on_speed_change(self, value):
        """Update the speed label when slider moves."""
        self._speed_label.config(text=f"{float(value):.2f}")

    def _on_hsv_change(self, attr: str, value: int):
        setattr(self._color_cfg, attr, value)

    def _on_save_hsv(self):
        mode = self.var_detect_mode.get()
        filename = f"color_{mode.lower().replace(' ', '_')}.json"
        self._color_cfg.to_json(filename)
        self.log(f"HSV config saved to {filename}")

    def _on_close(self):
        self.stop_pulse()
        self._running = False
        self._user_action = "quit"


# ══════════════════════════════════════════════════════════════════
#  GUI PIPELINE — event-driven orchestrator using root.after()
# ══════════════════════════════════════════════════════════════════

class GUIPipeline:

    TICK_MS = 33  # ~30 FPS

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
        self.robot_cfg  = robot_cfg
        self.send_robot = send_robot
        self.color_cfg  = color_cfg

        # Vision — build all detectors, start with "Orange Cube"
        self.cam_mgr     = CameraManager(cam_cfg)
        self._detectors  = {name: build_detector(name, cam_cfg) for name in DETECTOR_PRESETS}
        self._detect_mode = "Orange Cube"
        self.detector    = self._detectors[self._detect_mode]
        self.color_cfg   = self.detector.color_cfg  # may be None for ArUco
        self.transformer = CoordinateTransformer(cam_cfg, robot_cfg, cube_size_m)
        self.tracker     = KalmanTracker()
        self.guard       = StabilityGuard(*stability)
        self.renderer    = OverlayRenderer()

        # Robot
        self.eki   = EkiManager()
        self.robot = RobotController(robot_cfg, self.eki)

        # Logger
        self.logger: Optional[DetectionLogger] = None
        if log_path:
            self.logger = DetectionLogger(log_path)

        # GUI — pass the active detector's color config (or fallback)
        gui_color = self.detector.color_cfg if self.detector.color_cfg else color_cfg
        self.gui = VisionGUI(gui_color, robot_cfg)

        # Wire packet logger: EkiManager → GUI terminal (thread-safe)
        self.eki.set_packet_callback(self._on_packet)

        # Pipeline state
        self.phase = PipelinePhase.IDLE
        self._connected = False          # True after successful TCP connect
        self.cap: Optional[cv2.VideoCapture] = None
        self._current_detection: Optional[DetectionResult] = None
        self._current_e6pos: Optional[str] = None
        self._robot_thread: Optional[threading.Thread] = None
        self._robot_thread_result: Optional[bool] = None
        self._jog_thread: Optional[threading.Thread] = None
        self._jog_thread_result: Optional[bool] = None
        self._follow_thread: Optional[threading.Thread] = None
        self._follow_active = False     # True while follow mode is on

        # FPS
        self._fps_time  = time.time()
        self._fps_count = 0
        self._fps_value = 0.0

    # ── Entry point ───────────────────────────────────────────────

    def run(self):
        self.gui.log("KUKA Vision Control Panel ready. Enter IP and click Connect.")
        try:
            self.cap = self.cam_mgr.open()
            self.gui.log("Camera opened successfully.")
        except RuntimeError as e:
            self.gui.log(f"Camera error: {e}")
            return

        if self.logger:
            self.logger.open()

        self.gui.root.after(self.TICK_MS, self._tick)
        self.gui.root.mainloop()
        self._cleanup()

    # ── Robot busy guard ─────────────────────────────────────────

    def _is_robot_busy(self) -> bool:
        """True if any robot thread (pipeline, jog, or follow) is currently running."""
        if self._robot_thread is not None and self._robot_thread.is_alive():
            return True
        if self._jog_thread is not None and self._jog_thread.is_alive():
            return True
        if self._follow_thread is not None and self._follow_thread.is_alive():
            return True
        return False

    # ── Core tick (called every ~33ms) ────────────────────────────

    def _tick(self):
        if not self.gui.is_running():
            self.gui.root.quit()
            return

        try:
            # 1. Grab frame and run detection
            frame, mask, result, stable, e6pos = self._process_frame()

            # 2. Update video displays
            if frame is not None:
                vis = self.renderer.draw(
                    frame, result, stable, e6pos,
                    self.robot.state,
                    awaiting_confirm=(self.phase == PipelinePhase.CONFIRMING),
                    detect_mode=self._detect_mode,
                )
                self.gui.update_feed(vis)
                if mask is not None:
                    self.gui.update_mask(mask)

            # 3. Update telemetry, XY plane and status
            self.gui.update_telemetry(
                result, stable,
                self.guard._stable_count, self.guard.required_frames,
                e6pos,
            )
            self.gui.update_xy_plane(result)
            self.gui.update_robot_state(self.robot.state)
            self._update_fps()

            # 4. Handle user button presses
            action = self.gui.poll_action()
            self._handle_action(action)

            # 5. Enable/disable jog buttons based on connection and thread state
            jog_ok = self._connected and not self._is_robot_busy()
            self.gui.set_jog_enabled(jog_ok)

            # 6. Advance state machine
            self._advance_phase(result, stable, e6pos)

            # 7. Check jog thread completion
            self._check_jog_thread()

            # 8. Follow mode — send move if active
            if self.phase == PipelinePhase.FOLLOWING:
                self._follow_tick(result)

        except Exception as e:
            tb = traceback.format_exc()
            self.gui.log_error("E-TICK", f"Tick error: {e}", tb)

        # Schedule next tick (always, even after errors)
        self.gui.root.after(self.TICK_MS, self._tick)

    # ── Frame processing ──────────────────────────────────────────

    def _process_frame(self):
        if self.cap is None:
            return None, None, None, False, None

        ret, frame = self.cap.read()
        if not ret:
            return None, None, None, False, None

        result, mask = self.detector.detect_with_mask(frame)
        e6pos  = None
        stable = False

        if result is not None:
            result.cx_px, result.cy_px = self.tracker.update(
                result.cx_px, result.cy_px)
            fh, fw = frame.shape[:2]
            result = self.transformer.transform(result, fw, fh)
            if result is not None and result.in_workspace:
                e6pos  = self.transformer.to_e6pos(result)
                stable = self.guard.is_stable(result)
        else:
            self.tracker.reset()
            self.guard.reset()

        return frame, mask, result, stable, e6pos

    # ── User action handler ───────────────────────────────────────

    def _handle_action(self, action: Optional[str]):
        if action is None:
            return

        if action == "quit":
            self.gui._running = False
            return

        if action == "estop":
            self._emergency_stop()
            return

        if action == "connect":
            self._do_connect()
            return

        if action == "capture" and self.phase == PipelinePhase.IDLE:
            self._do_capture()
            return

        if action == "confirm" and self.phase == PipelinePhase.CONFIRMING:
            self._do_confirm()
            return

        if action == "skip" and self.phase == PipelinePhase.CONFIRMING:
            self._do_skip()
            return

        if action == "disconnect":
            self._do_disconnect()
            return

        if action == "jog":
            self._do_jog()
            return

        if action == "read_pos":
            self._do_read_position()
            return

        if action == "follow":
            self._do_follow_toggle()
            return

        if action == "set_speed":
            self._do_set_speed()
            return

        if action == "detect_mode":
            self._do_switch_detector()
            return

    # ── State machine ─────────────────────────────────────────────

    def _advance_phase(self, result, stable, e6pos):

        # ── IDLE: camera always detects ──
        if self.phase == PipelinePhase.IDLE:
            # Keep the latest detection available for capture
            if result is not None and result.in_workspace and e6pos is not None:
                self._current_detection = result
                self._current_e6pos = e6pos

        # ── EXECUTING: wait for robot thread to finish ──
        elif self.phase == PipelinePhase.EXECUTING:
            if self._robot_thread is not None and not self._robot_thread.is_alive():
                success = self._robot_thread_result
                self._robot_thread = None
                if success:
                    self.gui.log("Pick-and-place complete ✓")
                    self.gui.set_response("Pick-and-place complete", True)
                else:
                    self.gui.log_error("E-PP02",
                        "Pick-and-place sequence returned failure")
                    self.gui.set_response("Pick-and-place failed", False)
                # Return to IDLE — user decides next action
                self.phase = PipelinePhase.IDLE
                self.gui.update_pipeline_state("IDLE")
                self.gui.clear_target()
                self.gui.buttons["capture"].config(state=tk.NORMAL)
                self.robot.state = RobotState.IDLE
                self.gui.update_robot_state(RobotState.IDLE)

    # ── Robot commands (background threaded) ───────────────────────

    def _do_connect(self):
        ip, port = self.gui.get_connection_info()
        if ip is None:
            return
        self.gui.log(f"Connecting to {ip}:{port}...")
        try:
            self.eki.connect(ip, port)
            self._connected = True
            self.send_robot = True
            self.gui.update_connection(True)
            self.gui.set_connected_buttons(True)
            self.gui.set_response(f"Connected to {ip}:{port}", True)
            self.gui.log(f"Connected to {ip}:{port}")
        except Exception as exc:
            tb = traceback.format_exc()
            self._connected = False
            self.gui.update_connection(False)
            self.gui.set_connected_buttons(False)
            self.gui.set_response(f"Connection failed: {exc}", False)
            self.gui.log_error("E-CON01", f"Connection to {ip}:{port} failed: {exc}", tb)

    def _do_disconnect(self):
        # Cancel follow mode if active
        if self._follow_active:
            self._follow_active = False
            self._follow_thread = None
            self.gui.set_follow_active(False)
            self.phase = PipelinePhase.IDLE
            self.gui.update_pipeline_state("IDLE")
            self.gui.buttons["capture"].config(state=tk.NORMAL)
        try:
            self.eki.close()
        except Exception as exc:
            tb = traceback.format_exc()
            self.gui.log_error("E-DIS01", f"Disconnect error: {exc}", tb)
        self._connected = False
        self.send_robot = False
        self.gui.update_connection(False)
        self.gui.set_connected_buttons(False)
        self.gui.log("Disconnected.")
        self.gui.set_response("Disconnected", True)

    def _do_capture(self):
        """Snapshot the current detection into the Target fields."""
        det = self._current_detection
        e6pos = self._current_e6pos
        if det is None or e6pos is None:
            self.gui.log("No valid detection to capture — point camera at cube")
            self.gui.set_response("No detection available", False)
            return

        if not det.in_workspace:
            self.gui.log("Detection is outside workspace — cannot capture")
            self.gui.set_response("Outside workspace", False)
            return

        # Fill target fields with captured coordinates
        det.robot_a = self.robot_cfg.robot_a
        det.robot_b = self.robot_cfg.robot_b
        self.gui.update_target(
            det.x_robot_mm, det.y_robot_mm, det.z_robot_mm,
            det.robot_a, det.robot_b,
            det.angle_deg)
        self.gui.log_detection(
            f">>> CAPTURED  X:{det.x_robot_mm:.1f} "
            f"Y:{det.y_robot_mm:.1f} Z:{det.z_robot_mm:.1f} "
            f"A:{self.robot_cfg.robot_a:.1f} "
            f"B:{self.robot_cfg.robot_b:.1f} "
            f"C:{det.angle_deg:.1f}")

        if self.logger:
            self.logger.log(det)

        # Transition to CONFIRMING — wait for user to press Confirm
        self.phase = PipelinePhase.CONFIRMING
        self.gui.set_awaiting_confirm(True)
        self.gui.update_pipeline_state("CONFIRM TARGET")
        self.gui.buttons["capture"].config(state=tk.DISABLED)
        self.gui.log(f"Target captured: {e6pos} — review and CONFIRM or SKIP")

    def _do_confirm(self):
        # Read the (possibly user-edited) target coordinates
        vals = self.gui.get_target_values()
        if vals is None:
            self.gui.log("Confirm aborted: invalid target coordinates")
            return

        x, y, z, a, b, c = vals
        self.gui.log(f"Target confirmed: X:{x:.1f} Y:{y:.1f} Z:{z:.1f} "
                     f"A:{a:.1f} B:{b:.1f} C:{c:.1f}")

        # Apply edited values back to the detection result
        det = self._current_detection
        if det is not None:
            det.x_robot_mm = x
            det.y_robot_mm = y
            det.z_robot_mm = z
            det.robot_a    = a
            det.robot_b    = b
            det.angle_deg  = c   # C axis maps to angle

        self.gui.set_awaiting_confirm(False)
        self.phase = PipelinePhase.EXECUTING
        self.gui.update_pipeline_state("EXECUTING...")

        if not self._connected:
            self.gui.log(f"[DRY-RUN] pick_and_place "
                         f"X:{x:.1f} Y:{y:.1f} Z:{z:.1f}")
            self._robot_thread_result = None
            self._robot_thread = threading.Thread(
                target=self._thread_dry_run, daemon=True)
            self._robot_thread.start()
        else:
            self._robot_thread_result = None
            self._robot_thread = threading.Thread(
                target=self._thread_pick_and_place, args=(det,), daemon=True)
            self._robot_thread.start()

    def _thread_pick_and_place(self, det: DetectionResult):
        try:
            self._robot_thread_result = self.robot.execute_pick_and_place(det)
        except Exception as exc:
            self._robot_thread_result = False
            tb = traceback.format_exc()
            try:
                self.gui.root.after(0, self.gui.log_error,
                                    "E-PP01", f"Pick-place thread crash: {exc}", tb)
            except Exception:
                pass

    def _thread_dry_run(self):
        time.sleep(2.0)
        self._robot_thread_result = True

    def _do_skip(self):
        self.gui.set_awaiting_confirm(False)
        self.gui.clear_target()
        self.phase = PipelinePhase.IDLE
        self.gui.update_pipeline_state("IDLE")
        self.gui.buttons["capture"].config(state=tk.NORMAL)
        self.gui.log("Skipped — capture again when ready")

    def _emergency_stop(self):
        self.phase = PipelinePhase.IDLE
        self.gui.set_awaiting_confirm(False)
        self.gui.clear_target()
        self.gui.update_pipeline_state("E-STOP")
        self.gui.buttons["capture"].config(state=tk.NORMAL)
        self.robot.state = RobotState.ERROR
        self.gui.update_robot_state(RobotState.ERROR)
        self._robot_thread = None
        self._robot_thread_result = None
        self._jog_thread = None
        self._jog_thread_result = None
        self._follow_active = False
        self._follow_thread = None
        self.gui.set_follow_active(False)
        self.gui.log("EMERGENCY STOP activated")

    # ── Manual jog commands ────────────────────────────────────────

    def _do_jog(self):
        if not self._connected:
            self.gui.log("Cannot jog: not connected")
            return
        if self._is_robot_busy():
            self.gui.log("Cannot jog: robot busy")
            return
        frame = self.gui.get_jog_frame()
        if frame is None:
            return
        x, y, z, a, b, c = frame
        self.gui.log(f"MOVE FRAME: X:{x:.1f} Y:{y:.1f} Z:{z:.1f} "
                     f"A:{a:.1f} B:{b:.1f} C:{c:.1f}")
        self._jog_thread_result = None
        self._jog_thread = threading.Thread(
            target=self._thread_jog, args=(x, y, z, a, b, c), daemon=True)
        self._jog_thread.start()

    def _thread_jog(self, x, y, z, a, b, c):
        try:
            self._jog_thread_result = self.robot.move_linear(x, y, z, a, b, c)
        except Exception as exc:
            self._jog_thread_result = False
            tb = traceback.format_exc()
            try:
                self.gui.root.after(0, self.gui.log_error,
                                    "E-JOG01", f"Jog thread crash: {exc}", tb)
            except Exception:
                pass

    def _do_read_position(self):
        if not self._connected:
            self.gui.log("Cannot read position: not connected")
            return
        if self._is_robot_busy():
            self.gui.log("Cannot read position: robot busy")
            return
        try:
            cart_pos = self.eki.getCurrentCartPos()
            f = cart_pos.frame
            self.gui.set_jog_frame(
                float(f.x), float(f.y), float(f.z),
                float(f.a), float(f.b), float(f.c),
            )
            self.gui.log(f"Read pos: X:{f.x} Y:{f.y} Z:{f.z} "
                         f"A:{f.a} B:{f.b} C:{f.c}")
            self.gui.set_response(
                f"X:{f.x} Y:{f.y} Z:{f.z} A:{f.a} B:{f.b} C:{f.c}", True)
        except Exception as exc:
            tb = traceback.format_exc()
            self.gui.log_error("E-RD01", f"Read position failed: {exc}", tb)
            self.gui.set_response(f"Read pos failed: {exc}", False)

    def _do_set_speed(self):
        if not self._connected:
            self.gui.log("Cannot set speed: not connected")
            return
        speed = self.gui.var_speed.get()
        try:
            self.eki.setCartSpeed(speed)
            self.gui.log(f"Cart speed set to {speed:.2f} m/s")
            self.gui.set_response(f"Speed: {speed:.2f} m/s", True)
        except Exception as exc:
            tb = traceback.format_exc()
            self.gui.log_error("E-SPD01", f"Set speed failed: {exc}", tb)
            self.gui.set_response(f"Set speed failed: {exc}", False)

    def _do_switch_detector(self):
        """Switch active detector based on GUI dropdown selection."""
        name = self.gui.var_detect_mode.get()
        if name == self._detect_mode:
            return  # no change

        if name not in self._detectors:
            self.gui.log(f"Unknown detector: {name}")
            return

        self._detect_mode = name
        self.detector = self._detectors[name]

        # Reset tracker and stability guard for the new detector
        self.tracker.reset()
        self.guard.reset()
        self._current_detection = None
        self._current_e6pos = None

        # Update HSV sliders if the new detector uses HSV
        if self.detector.uses_hsv() and self.detector.color_cfg is not None:
            self.color_cfg = self.detector.color_cfg
            self.gui._color_cfg = self.detector.color_cfg
            # Sync slider values to the new detector's color config
            for attr, var in self.gui.hsv_vars.items():
                var.set(getattr(self.detector.color_cfg, attr))
            # Enable HSV sliders
            for child in self.gui.hsv_vars.values():
                pass  # IntVars don't have state — scales are always active
            self.gui.log(f"Detector: {name} (HSV tuner active)")
        else:
            self.gui.log(f"Detector: {name} (no HSV tuner)")

    def _check_jog_thread(self):
        if self._jog_thread is not None and not self._jog_thread.is_alive():
            success = self._jog_thread_result
            self._jog_thread = None
            if success:
                self.gui.log("Move completed successfully")
                self.gui.set_response("Move completed successfully", True)
            else:
                self.gui.log("Move FAILED")
                self.gui.set_response("Move FAILED", False)
                self.robot.state = RobotState.ERROR
                self.gui.update_robot_state(RobotState.ERROR)

    # ── Follow mode ─────────────────────────────────────────────────

    def _do_follow_toggle(self):
        """Toggle follow mode on/off."""
        if self._follow_active:
            # Stop following
            self._follow_active = False
            self.gui.set_follow_active(False)
            self.phase = PipelinePhase.IDLE
            self.gui.update_pipeline_state("IDLE")
            self.gui.buttons["capture"].config(state=tk.NORMAL)
            self.robot.state = RobotState.IDLE
            self.gui.update_robot_state(RobotState.IDLE)
            self.gui.log("Follow mode OFF")
            return

        # Start following
        if not self._connected:
            self.gui.log("Cannot follow: not connected")
            return
        if self.phase != PipelinePhase.IDLE:
            self.gui.log("Cannot follow: pipeline busy")
            return

        self._follow_active = True
        self.phase = PipelinePhase.FOLLOWING
        self.gui.set_follow_active(True)
        self.gui.update_pipeline_state("FOLLOWING")
        self.gui.buttons["capture"].config(state=tk.DISABLED)
        self.robot.state = RobotState.APPROACHING
        self.gui.update_robot_state(RobotState.APPROACHING)
        self.gui.log("Follow mode ON -- robot will track detected cube")

    def _follow_tick(self, result):
        """Called every tick while FOLLOWING. Sends move if detection valid and no thread running."""
        if not self._follow_active or self.phase != PipelinePhase.FOLLOWING:
            return

        # Wait for previous follow move to finish
        if self._follow_thread is not None and self._follow_thread.is_alive():
            return

        # Check previous follow thread result
        if self._follow_thread is not None:
            self._follow_thread = None  # clean up finished thread

        if result is None or not result.in_workspace:
            return

        # Build target: use detected X/Y, fixed Z (pick_height + approach clearance), fixed A/B, detected C
        r = self.robot_cfg
        x = result.x_robot_mm
        y = result.y_robot_mm
        z = r.pick_height_mm + r.approach_clearance_mm
        a = r.robot_a
        b = r.robot_b
        c = result.angle_deg

        self._follow_thread = threading.Thread(
            target=self._thread_follow_move, args=(x, y, z, a, b, c),
            daemon=True)
        self._follow_thread.start()

    def _thread_follow_move(self, x, y, z, a, b, c):
        """Background thread for a single follow move."""
        try:
            self.robot.move_linear(x, y, z, a, b, c)
        except Exception as exc:
            tb = traceback.format_exc()
            try:
                self.gui.root.after(0, self.gui.log_error,
                                    "E-FOL01", f"Follow move error: {exc}", tb)
            except Exception:
                pass

    # ── Packet logger callback ─────────────────────────────────────

    def _on_packet(self, direction: str, data: str):
        """Called from EkiManager (possibly background thread) — schedule on GUI thread."""
        try:
            self.gui.root.after(0, self.gui.log_packet, direction, data)
        except Exception:
            pass

    # ── FPS and cleanup ───────────────────────────────────────────

    def _update_fps(self):
        self._fps_count += 1
        now = time.time()
        elapsed = now - self._fps_time
        if elapsed >= 1.0:
            self._fps_value = self._fps_count / elapsed
            self._fps_count = 0
            self._fps_time = now
            self.gui.update_fps(self._fps_value)

    def _cleanup(self):
        self.cam_mgr.release()
        if self.logger:
            self.logger.close()
        if self._connected:
            self.eki.close()
            self._connected = False


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    COLOR_JSON = "color_config.json"
    CAM_JSON   = "camera_config.json"
    ROBOT_JSON = "robot_config.json"

    cam_cfg   = CameraConfig.from_json(CAM_JSON)   if Path(CAM_JSON).exists()   else CameraConfig()
    robot_cfg = RobotConfig.from_json(ROBOT_JSON)   if Path(ROBOT_JSON).exists() else RobotConfig()
    color_cfg = ColorConfig.from_json(COLOR_JSON)   if Path(COLOR_JSON).exists() else ColorConfig()

    pipeline = GUIPipeline(
        cam_cfg     = cam_cfg,
        robot_cfg   = robot_cfg,
        color_cfg   = color_cfg,
        cube_size_m = 0.05,
        log_path    = "detections.csv",
        send_robot  = False,    # flip to True for real robot
        stability   = (5, 5.0),
    )
    pipeline.run()


