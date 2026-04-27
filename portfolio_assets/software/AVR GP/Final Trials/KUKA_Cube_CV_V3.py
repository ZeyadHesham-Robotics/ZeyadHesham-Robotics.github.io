"""
kuka_vision.py
==============
OOP vision pipeline for orange cube detection → KUKA robot EKI pick & place.

Sequence
--------
1. Robot moves to HOME position
2. Camera detects cube → computes E6POS
3. Robot moves to APPROACH (above cube)
4. Robot moves DOWN to PICK position
5. Gripper closes (picks cube)
6. Robot lifts back to APPROACH
7. Robot moves to PLACE position
8. Gripper opens (places cube)
9. Robot returns to HOME

Classes
-------
CameraConfig          – camera parameters & intrinsics
RobotConfig           – robot transform & workspace limits
ColorConfig           – HSV segmentation parameters
DetectionResult       – dataclass for a single detection
KalmanTracker         – 2-D position smoother
CubeDetector          – frame-level detection logic
CoordinateTransformer – camera → robot coordinate math
StabilityGuard        – emit a pose only after N stable frames
EkiManager            – EKI XML socket communication with KUKA
RobotController       – high-level motion commands (home, pick, place)
DetectionLogger       – CSV logging
OverlayRenderer       – debug overlay on live frame
CameraManager         – VideoCapture open/release
VisionPipeline        – top-level orchestrator
"""

import cv2
import numpy as np
import socket
import json
import time
import csv
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from enum import Enum, auto


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


# ══════════════════════════════════════════════════════════════════
#  CONFIG DATACLASSES
# ══════════════════════════════════════════════════════════════════

@dataclass
class CameraConfig:
    index: int          = 1
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
    # ── Camera-to-robot rigid transform (measure precisely!) ──
    cam_offset_x: float  =  600.0   # mm
    cam_offset_y: float  =    0.0
    cam_offset_z: float  =  800.0

    # ── Fixed orientation sent in every E6POS ──
    robot_a: float       =  180.0
    robot_b: float       =    0.0

    # ── Workspace safety limits ──
    workspace_x: tuple   = (300.0, 900.0)
    workspace_y: tuple   = (-400.0, 400.0)

    # ── EKI connection ──
    tcp_ip: str          = "192.168.1.1"
    tcp_port: int        = 54610

    # ── Pick & place geometry ──
    approach_clearance_mm: float = 80.0   # how high above cube to approach
    pick_z_offset_mm: float      =  0.0   # fine-tune exact pick height
    place_x_mm: float            = 500.0  # fixed place position X
    place_y_mm: float            = 300.0  # fixed place position Y
    place_z_mm: float            = 200.0  # fixed place position Z
    place_a_mm: float            = 180.0
    place_b_mm: float            =   0.0
    place_c_mm: float            =   0.0

    # ── Home joint angles (degrees) ──
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
    lower_h: int     =   8
    lower_s: int     = 100
    lower_v: int     = 100
    upper_h: int     =  35
    upper_s: int     = 255
    upper_v: int     = 255
    min_area: int    = 1500
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
    in_workspace: bool = False
    timestamp: float   = field(default_factory=time.time)


# ══════════════════════════════════════════════════════════════════
#  EKI MANAGER
#  Communicates with KUKA EKI (Ethernet KRL Interface) over TCP.
#
#  KRL-side EKI XML schema (EKI_KukaVision.xml)
#  ─────────────────────────────────────────────
#  Receive tag (PC → Robot):
#    <RobotCommand>
#      <Cmd>STRING</Cmd>          MOVEJ | MOVEL | GRIPPER | STATUS
#      <X>REAL</X> <Y>REAL</Y> <Z>REAL</Z>
#      <A>REAL</A> <B>REAL</B> <C>REAL</C>
#      <A1>REAL</A1> ... <A6>REAL</A6>
#      <GripperCmd>STRING</GripperCmd>   OPEN | CLOSE
#    </RobotCommand>
#
#  Send tag (Robot → PC):
#    <RobotFeedback>
#      <Status>STRING</Status>    BUSY | DONE | ERROR
#      <X>REAL</X> ... <C>REAL</C>
#    </RobotFeedback>
# ══════════════════════════════════════════════════════════════════

class EkiManager:

    RECV_BUFFER   = 4096
    POLL_INTERVAL = 0.05
    TIMEOUT       = 30.0

    def __init__(self):
        self._sock: Optional[socket.socket] = None
        self.connected = False

    # ── Connection ────────────────────────────────────────────────

    def connect(self, ip: str, port: int) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._sock.settimeout(5.0)
            self._sock.connect((ip, port))
            self._sock.settimeout(None)
            self.connected = True
            print(f"✅ EKI connected → {ip}:{port}")
            return True
        except Exception as exc:
            print(f"❌ EKI connect failed: {exc}")
            self.connected = False
            return False

    def disconnect(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self.connected = False
        print("🔌 EKI disconnected")

    # ── Low-level send / receive ───────────────────────────────────

    def _send_xml(self, xml_str: str) -> bool:
        if not self.connected:
            print("❌ EKI not connected")
            return False
        try:
            self._sock.sendall((xml_str + "\0").encode("utf-8"))
            return True
        except Exception as exc:
            print(f"❌ EKI send error: {exc}")
            self.connected = False
            return False

    def _recv_xml(self, timeout: float = 5.0) -> Optional[ET.Element]:
        if not self._sock:
            return None
        try:
            self._sock.settimeout(timeout)
            data = b""
            while True:
                chunk = self._sock.recv(self.RECV_BUFFER)
                if not chunk:
                    break
                data += chunk
                if b"\0" in data or b"</RobotFeedback>" in data:
                    break
            self._sock.settimeout(None)
            xml_str = data.decode("utf-8").replace("\0", "").strip()
            return ET.fromstring(xml_str)
        except socket.timeout:
            return None
        except Exception as exc:
            print(f"❌ EKI recv error: {exc}")
            return None

    # ── XML command builders ──────────────────────────────────────

    @staticmethod
    def _cart_xml(cmd: str, x, y, z, a, b, c) -> str:
        return (
            f"<RobotCommand><Cmd>{cmd}</Cmd>"
            f"<X>{x:.3f}</X><Y>{y:.3f}</Y><Z>{z:.3f}</Z>"
            f"<A>{a:.3f}</A><B>{b:.3f}</B><C>{c:.3f}</C>"
            f"</RobotCommand>"
        )

    @staticmethod
    def _joint_xml(a1, a2, a3, a4, a5, a6) -> str:
        return (
            f"<RobotCommand><Cmd>MOVEJ</Cmd>"
            f"<A1>{a1:.3f}</A1><A2>{a2:.3f}</A2><A3>{a3:.3f}</A3>"
            f"<A4>{a4:.3f}</A4><A5>{a5:.3f}</A5><A6>{a6:.3f}</A6>"
            f"</RobotCommand>"
        )

    @staticmethod
    def _gripper_xml(action: str) -> str:
        return (
            f"<RobotCommand><Cmd>GRIPPER</Cmd>"
            f"<GripperCmd>{action}</GripperCmd>"
            f"</RobotCommand>"
        )

    # ── Wait for DONE feedback ────────────────────────────────────

    def _wait_done(self, timeout: float = None) -> bool:
        timeout = timeout or self.TIMEOUT
        start   = time.time()
        while time.time() - start < timeout:
            fb = self._recv_xml(timeout=self.POLL_INTERVAL * 10)
            if fb is None:
                time.sleep(self.POLL_INTERVAL)
                continue
            status = fb.findtext("Status", "").strip().upper()
            if status == "DONE":
                return True
            if status == "ERROR":
                print("❌ Robot reported ERROR in feedback")
                return False
            time.sleep(self.POLL_INTERVAL)
        print("⏱ EKI wait_done timed out")
        return False

    # ── Public motion API ─────────────────────────────────────────

    def move_linear(self, x, y, z, a, b, c, wait=True) -> bool:
        """Cartesian linear move (MOVEL)."""
        if not self._send_xml(self._cart_xml("MOVEL", x, y, z, a, b, c)):
            return False
        return self._wait_done() if wait else True

    def move_joint(self, a1, a2, a3, a4, a5, a6, wait=True) -> bool:
        """Joint-space move (MOVEJ)."""
        if not self._send_xml(self._joint_xml(a1, a2, a3, a4, a5, a6)):
            return False
        return self._wait_done() if wait else True

    def gripper_open(self, wait=True) -> bool:
        if not self._send_xml(self._gripper_xml("OPEN")):
            return False
        return self._wait_done(timeout=5.0) if wait else True

    def gripper_close(self, wait=True) -> bool:
        if not self._send_xml(self._gripper_xml("CLOSE")):
            return False
        return self._wait_done(timeout=5.0) if wait else True

    def get_status(self) -> Optional[str]:
        self._send_xml("<RobotCommand><Cmd>STATUS</Cmd></RobotCommand>")
        fb = self._recv_xml(timeout=3.0)
        return fb.findtext("Status", "UNKNOWN").strip() if fb is not None else None


# ══════════════════════════════════════════════════════════════════
#  ROBOT CONTROLLER
#  High-level pick-and-place sequence built on EkiManager.
# ══════════════════════════════════════════════════════════════════

class RobotController:
    """
    Executes the full pick-and-place sequence:
      HOME → APPROACH → PICK → LIFT → PLACE → HOME
    """

    def __init__(self, robot_cfg: RobotConfig, eki: EkiManager):
        self.cfg   = robot_cfg
        self.eki   = eki
        self.state = RobotState.IDLE

    def _set_state(self, state: RobotState):
        self.state = state
        print(f"  🤖 [{state.name}]")

    # ── Individual motion steps ───────────────────────────────────

    def go_home(self) -> bool:
        self._set_state(RobotState.HOMING)
        c  = self.cfg
        ok = self.eki.move_joint(
            c.home_a1, c.home_a2, c.home_a3,
            c.home_a4, c.home_a5, c.home_a6,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
        return ok

    def approach_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.APPROACHING)
        c  = self.cfg
        ok = self.eki.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.approach_clearance_mm,
            c.robot_a, c.robot_b, det.angle_deg,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
        return ok

    def pick_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.PICKING)
        c = self.cfg

        # 1 — Open gripper
        if not self.eki.gripper_open():
            self._set_state(RobotState.ERROR)
            return False

        # 2 — Lower to pick height
        ok = self.eki.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.pick_z_offset_mm,
            c.robot_a, c.robot_b, det.angle_deg,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
            return False

        # 3 — Close gripper
        if not self.eki.gripper_close():
            self._set_state(RobotState.ERROR)
            return False

        return True

    def lift_cube(self, det: DetectionResult) -> bool:
        self._set_state(RobotState.LIFTING)
        c  = self.cfg
        ok = self.eki.move_linear(
            det.x_robot_mm,
            det.y_robot_mm,
            det.z_robot_mm + c.approach_clearance_mm,
            c.robot_a, c.robot_b, det.angle_deg,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
        return ok

    def place_cube(self) -> bool:
        self._set_state(RobotState.PLACING)
        c = self.cfg

        # 1 — Move above place position
        ok = self.eki.move_linear(
            c.place_x_mm, c.place_y_mm,
            c.place_z_mm + c.approach_clearance_mm,
            c.place_a_mm, c.place_b_mm, c.place_c_mm,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
            return False

        # 2 — Lower to place position
        ok = self.eki.move_linear(
            c.place_x_mm, c.place_y_mm, c.place_z_mm,
            c.place_a_mm, c.place_b_mm, c.place_c_mm,
        )
        if not ok:
            self._set_state(RobotState.ERROR)
            return False

        # 3 — Open gripper (release)
        if not self.eki.gripper_open():
            self._set_state(RobotState.ERROR)
            return False

        return True

    # ── Full sequence ─────────────────────────────────────────────

    def execute_pick_and_place(self, det: DetectionResult) -> bool:
        """
        Run the complete sequence for one cube detection.
        Returns True if all steps succeeded.
        On any failure, attempts a safe return to HOME.
        """
        print("\n━━━ PICK & PLACE SEQUENCE ━━━")

        steps = [
            ("Approach", lambda: self.approach_cube(det)),
            ("Pick",     lambda: self.pick_cube(det)),
            ("Lift",     lambda: self.lift_cube(det)),
            ("Place",    lambda: self.place_cube()),
            ("Return",   lambda: self._return_home()),
        ]

        for name, step_fn in steps:
            print(f"  ▶ {name}")
            if not step_fn():
                print(f"  ❌ Step '{name}' FAILED — attempting safe recovery")
                self.go_home()   # best-effort recovery
                return False

        self._set_state(RobotState.IDLE)
        print("━━━ SEQUENCE COMPLETE ━━━\n")
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
        return float(corrected[0]), float(corrected[1])

    def reset(self):
        self._initialized = False


# ══════════════════════════════════════════════════════════════════
#  CUBE DETECTOR
# ══════════════════════════════════════════════════════════════════

class CubeDetector:
    def __init__(self, color_cfg: ColorConfig):
        self.color_cfg = color_cfg
        self.kernel    = cv2.getStructuringElement(
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

    def detect_with_mask(
        self, frame: np.ndarray
    ) -> tuple[Optional[DetectionResult], np.ndarray]:
        mask      = self.build_mask(frame)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None, mask

        c    = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < self.color_cfg.min_area:
            return None, mask

        rect              = cv2.minAreaRect(c)
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


# ══════════════════════════════════════════════════════════════════
#  COORDINATE TRANSFORMER
# ══════════════════════════════════════════════════════════════════

class CoordinateTransformer:
    def __init__(self, cam_cfg: CameraConfig, robot_cfg: RobotConfig,
                 cube_size_m: float = 0.05):
        self.cam_cfg     = cam_cfg
        self.robot_cfg   = robot_cfg
        self.cube_size_m = cube_size_m
        self.cx0, self.cy0 = cam_cfg.principal_point()

    def transform(self, result: DetectionResult) -> Optional[DetectionResult]:
        if result.pixel_size <= 1:
            return None
        Z = (self.cam_cfg.fx * self.cube_size_m) / result.pixel_size
        X = ((result.cx_px - self.cx0) * Z) / self.cam_cfg.fx
        Y = ((result.cy_px - self.cy0) * Z) / self.cam_cfg.fy

        result.x_cam_mm = X * 1000.0
        result.y_cam_mm = Y * 1000.0
        result.z_cam_mm = Z * 1000.0

        result.x_robot_mm = self.robot_cfg.cam_offset_x + result.x_cam_mm
        result.y_robot_mm = self.robot_cfg.cam_offset_y - result.y_cam_mm
        result.z_robot_mm = self.robot_cfg.cam_offset_z - result.z_cam_mm

        wx_lo, wx_hi = self.robot_cfg.workspace_x
        wy_lo, wy_hi = self.robot_cfg.workspace_y
        result.in_workspace = (
            wx_lo < result.x_robot_mm < wx_hi
            and wy_lo < result.y_robot_mm < wy_hi
        )
        return result

    def to_e6pos(self, result: DetectionResult) -> str:
        return (
            f"{{X {result.x_robot_mm:.2f}, Y {result.y_robot_mm:.2f}, "
            f"Z {result.z_robot_mm:.2f}, A {self.robot_cfg.robot_a:.2f}, "
            f"B {self.robot_cfg.robot_b:.2f}, C {result.angle_deg:.2f}}}"
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
        frame:       np.ndarray,
        result:      Optional[DetectionResult],
        stable:      bool,
        e6pos:       Optional[str],
        robot_state: RobotState = RobotState.IDLE,
    ) -> np.ndarray:
        out = frame.copy()
        self._update_fps()

        # FPS
        cv2.putText(out, f"FPS: {self._fps_display:.1f}",
                    (10, out.shape[0] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.CYAN, 1)

        # Robot state banner (top-right)
        state_color = self.GREEN if robot_state == RobotState.IDLE else self.ORANGE
        cv2.putText(out, f"ROBOT: {robot_state.name}",
                    (out.shape[1] - 230, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, state_color, 2)

        if result is None:
            cv2.putText(out, "No detection", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.RED, 2)
            return out

        # Bounding box
        color = self.GREEN if result.in_workspace else self.RED
        cv2.drawContours(out, [result.box], 0, color, 2)

        # Centre dot
        cx_i, cy_i = int(result.cx_px), int(result.cy_px)
        cv2.circle(out, (cx_i, cy_i), 8, self.RED, -1)

        # Angle arrow
        rad = np.deg2rad(result.angle_deg)
        cv2.line(out, (cx_i, cy_i),
                 (int(cx_i + 40 * np.cos(rad)), int(cy_i - 40 * np.sin(rad))),
                 self.YELLOW, 2)

        # Telemetry
        lines = [
            f"Camera  (mm): {result.x_cam_mm:.1f}, {result.y_cam_mm:.1f}, {result.z_cam_mm:.1f}",
            f"Robot   (mm): {result.x_robot_mm:.1f}, {result.y_robot_mm:.1f}, {result.z_robot_mm:.1f}",
            f"Angle  (deg): {result.angle_deg:.1f}",
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
                print(f"✅ Saved to {self.output_path}")
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
#  VISION PIPELINE — top-level orchestrator
# ══════════════════════════════════════════════════════════════════

class VisionPipeline:
    """
    Full cycle
    ----------
    1.  Robot → HOME (joint move)
    2.  Camera detects & stabilises cube pose
    3.  RobotController.execute_pick_and_place()
        a. APPROACH  — move above cube
        b. PICK      — open gripper → lower → close gripper
        c. LIFT      — raise to approach height
        d. PLACE     — move above place → lower → open gripper
        e. RETURN    — go HOME
    4.  Repeat from step 1
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

    # ── Robot connection ──────────────────────────────────────────

    def _connect_robot(self) -> bool:
        if not self.send_robot:
            print("ℹ️  DRY-RUN mode — EKI not connected")
            return True
        return self.eki.connect(self.robot_cfg.tcp_ip, self.robot_cfg.tcp_port)

    # ── Main loop ─────────────────────────────────────────────────

    def run(self):
        if not self._connect_robot():
            print("❌ Robot connection failed. Exiting.")
            return

        cap = self.cam_mgr.open()
        if self.logger:
            self.logger.open()

        print("🚀 Pipeline running  |  Q = quit")

        try:
            while True:

                # ── 1. Go HOME ───────────────────────────────────
                if self.send_robot:
                    print("\n🏠 Moving to HOME...")
                    if not self.robot.go_home():
                        print("❌ Home move failed.")
                        break

                # ── 2. Detect cube ───────────────────────────────
                print("👁  Waiting for stable cube detection...")
                detection = self._wait_for_stable_detection(cap)

                if detection is None:
                    break   # user pressed Q

                e6pos = self.transformer.to_e6pos(detection)
                print(f"📍 Cube at: {e6pos}")

                if self.logger:
                    self.logger.log(detection)

                # ── 3. Pick & place ──────────────────────────────
                if self.send_robot:
                    success = self.robot.execute_pick_and_place(detection)
                    if not success:
                        print("⚠️  Sequence failed — retrying from HOME")
                else:
                    print(f"[DRY-RUN] execute_pick_and_place({e6pos})")
                    time.sleep(2.0)

        finally:
            self.cam_mgr.release()
            cv2.destroyAllWindows()
            if self.logger:
                self.logger.close()
            if self.send_robot:
                self.eki.disconnect()
            print("🛑 Pipeline stopped.")

    # ── Detection loop ────────────────────────────────────────────

    def _wait_for_stable_detection(
        self, cap: cv2.VideoCapture
    ) -> Optional[DetectionResult]:
        """
        Continuously grabs frames and runs the vision stack until a
        stable detection is achieved. Returns the result or None if
        the user presses Q.
        """
        self.tracker.reset()
        self.guard.reset()

        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️  Frame grab failed")
                return None

            result, mask = self.detector.detect_with_mask(frame)
            e6pos  = None
            stable = False

            if result is not None:
                result.cx_px, result.cy_px = self.tracker.update(
                    result.cx_px, result.cy_px
                )
                result = self.transformer.transform(result)

                if result is not None and result.in_workspace:
                    e6pos  = self.transformer.to_e6pos(result)
                    stable = self.guard.is_stable(result)
                    if stable:
                        return result   # ← stable pose found
            else:
                self.tracker.reset()
                self.guard.reset()

            vis = self.renderer.draw(
                frame, result, stable, e6pos, self.robot.state
            )
            cv2.imshow("Vision → KUKA", vis)
            cv2.imshow("Mask",          mask)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                return None


# ══════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    COLOR_JSON = "color_config.json"
    CAM_JSON   = "camera_config.json"
    ROBOT_JSON = "robot_config.json"

    cam_cfg   = CameraConfig.from_json(CAM_JSON)   if Path(CAM_JSON).exists()   else CameraConfig()
    robot_cfg = RobotConfig.from_json(ROBOT_JSON)  if Path(ROBOT_JSON).exists() else RobotConfig()
    color_cfg = ColorConfig.from_json(COLOR_JSON)  if Path(COLOR_JSON).exists() else ColorConfig()

    # Uncomment to calibrate colors before running:
    HSVTuner(cam_cfg.index, cam_cfg.backend, COLOR_JSON).run()

    pipeline = VisionPipeline(
        cam_cfg     = cam_cfg,
        robot_cfg   = robot_cfg,
        color_cfg   = color_cfg,
        cube_size_m = 0.05,
        log_path    = "detections.csv",
        send_robot  = False,    # ← flip to True once dry-run is verified
        stability   = (5, 5.0),
    )
    pipeline.run()

