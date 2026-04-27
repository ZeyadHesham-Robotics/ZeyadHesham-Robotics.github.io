"""
VISION + KUKA PICK & PLACE (FULL INTEGRATED VERSION)
"""

import cv2
import numpy as np
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ============================
# KUKA IMPORTS
# ============================
from EkiManager import EkiManager
from JointPosition import JointPosition


# =========================================================
# CONFIGS
# =========================================================

@dataclass
class CameraConfig:
    index: int = 1
    width: int = 640
    height: int = 480
    fx: float = 800.0
    fy: float = 800.0
    backend: int = cv2.CAP_MSMF


@dataclass
class RobotConfig:
    cam_offset_x: float = 600.0
    cam_offset_y: float = 0.0
    cam_offset_z: float = 800.0
    robot_a: float = 180.0
    robot_b: float = 0.0
    workspace_x: tuple = (300.0, 900.0)
    workspace_y: tuple = (-400.0, 400.0)
    tcp_ip: str = "192.168.1.1"
    tcp_port: int = 54610


# =========================================================
# ROBOT CONTROLLER
# =========================================================

class RobotController:

    def __init__(self, cfg: RobotConfig):
        self.cfg = cfg
        self.eki = EkiManager()
        self.eki.connect(cfg.tcp_ip, cfg.tcp_port)

        self.homePos = JointPosition([0, -90, 90, 0, 90, -90], [0]*6)
        self.place_zone = [1000, 300, 800, 180, 0, 0]
        self.safe_height = 100

        print("✅ Robot connected.")

    def go_home(self):
        print("🏠 Moving HOME")
        self.eki.goToJointPos(self.homePos)

    def move_cartesian(self, X, Y, Z, A, B, C):
        cartPos = self.eki.getCurrentCartPos()
        cartPos.set_frame([X, Y, Z, A, B, C])
        self.eki.goToCartesianPos(cartPos.asArray())

    def wait_step(self, message):
        input(f"\n🔘 {message}")

    def pick_and_place(self, X, Y, Z, A, B, C):

        self.wait_step("Press ENTER → Move above cube")
        self.move_cartesian(X, Y, Z + self.safe_height, A, B, C)

        self.wait_step("Press ENTER → Descend to cube")
        self.move_cartesian(X, Y, Z, A, B, C)

        print("🤖 Close gripper here")
        time.sleep(1)

        self.wait_step("Press ENTER → Lift cube")
        self.move_cartesian(X, Y, Z + self.safe_height, A, B, C)

        self.wait_step("Press ENTER → Move to place zone")
        px, py, pz, pa, pb, pc = self.place_zone
        self.move_cartesian(px, py, pz + self.safe_height, pa, pb, pc)
        self.move_cartesian(px, py, pz, pa, pb, pc)

        print("🤖 Open gripper here")
        time.sleep(1)

        self.move_cartesian(px, py, pz + self.safe_height, pa, pb, pc)

        self.wait_step("Press ENTER → Return HOME")
        self.go_home()

        print("✅ Pick & Place Finished")


# =========================================================
# DETECTION RESULT
# =========================================================

@dataclass
class DetectionResult:
    cx_px: float
    cy_px: float
    pixel_size: float
    angle_deg: float
    x_robot_mm: float = 0.0
    y_robot_mm: float = 0.0
    z_robot_mm: float = 0.0
    timestamp: float = field(default_factory=time.time)


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    cam_cfg = CameraConfig()
    robot_cfg = RobotConfig()

    robot = RobotController(robot_cfg)
    robot.go_home()

    cap = cv2.VideoCapture(cam_cfg.index, cam_cfg.backend)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cam_cfg.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cam_cfg.height)

    print("🚀 System running | Press q to quit")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            blurred = cv2.GaussianBlur(frame, (7, 7), 0)
            hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

            lower = np.array([8, 100, 100])
            upper = np.array([35, 255, 255])
            mask = cv2.inRange(hsv, lower, upper)

            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if contours:
                c = max(contours, key=cv2.contourArea)
                area = cv2.contourArea(c)

                if area > 1500:
                    rect = cv2.minAreaRect(c)
                    (cx, cy), (w, h), angle = rect
                    pixel_size = max(w, h)

                    if pixel_size > 1:
                        Z = (cam_cfg.fx * 0.05) / pixel_size
                        X = ((cx - cam_cfg.width/2) * Z) / cam_cfg.fx
                        Y = ((cy - cam_cfg.height/2) * Z) / cam_cfg.fy

                        x_robot = robot_cfg.cam_offset_x + X * 1000
                        y_robot = robot_cfg.cam_offset_y - Y * 1000
                        z_robot = robot_cfg.cam_offset_z - Z * 1000

                        print("\n🎯 Cube detected at:", x_robot, y_robot, z_robot)

                        robot.wait_step("Press ENTER → Start Pick & Place")
                        robot.pick_and_place(
                            x_robot,
                            y_robot,
                            z_robot,
                            robot_cfg.robot_a,
                            robot_cfg.robot_b,
                            angle
                        )

            cv2.imshow("Vision", frame)
            cv2.imshow("Mask", mask)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("🛑 System stopped.")
        
        