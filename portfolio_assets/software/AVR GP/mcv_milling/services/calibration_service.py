"""
MCV Fiber Milling - Two-Tag ArUco Calibration Engine

Computes $BASE correction from table reference tag and workpiece tag detections
using an eye-in-hand camera on a KUKA KR120 R2100.
"""

import numpy as np
import cv2
import json
import logging
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)


def kuka_abc_to_matrix(x, y, z, a_deg, b_deg, c_deg):
    """
    Build 4x4 homogeneous transform from KUKA [X,Y,Z,A,B,C].
    KUKA convention: A=Rz, B=Ry, C=Rx (ZYX extrinsic Euler).
    Units: mm for translation, degrees for angles.
    """
    A = np.radians(a_deg)
    B = np.radians(b_deg)
    C = np.radians(c_deg)

    Rz = np.array([[np.cos(A), -np.sin(A), 0],
                    [np.sin(A),  np.cos(A), 0],
                    [0,          0,         1]])
    Ry = np.array([[ np.cos(B), 0, np.sin(B)],
                    [ 0,         1, 0        ],
                    [-np.sin(B), 0, np.cos(B)]])
    Rx = np.array([[1, 0,          0         ],
                    [0, np.cos(C), -np.sin(C)],
                    [0, np.sin(C),  np.cos(C)]])

    R = Rz @ Ry @ Rx
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [x, y, z]
    return T


def matrix_to_kuka_abc(T):
    """
    Extract [X, Y, Z, A, B, C] from 4x4 homogeneous transform.
    Returns tuple of 6 floats (mm, degrees).
    """
    x, y, z = T[0, 3], T[1, 3], T[2, 3]
    R = T[:3, :3]

    sy = np.sqrt(R[0, 0]**2 + R[1, 0]**2)
    singular = sy < 1e-6

    if not singular:
        C = np.arctan2(R[2, 1], R[2, 2])
        B = np.arctan2(-R[2, 0], sy)
        A = np.arctan2(R[1, 0], R[0, 0])
    else:
        C = np.arctan2(-R[1, 2], R[1, 1])
        B = np.arctan2(-R[2, 0], sy)
        A = 0.0

    return (float(x), float(y), float(z),
            float(np.degrees(A)), float(np.degrees(B)), float(np.degrees(C)))


def detect_aruco_pose(gray_image, tag_id, tag_size_mm, camera_matrix, dist_coeffs,
                      aruco_dict_type='DICT_6X6_250'):
    """
    Detect a specific ArUco tag and return its 4x4 pose matrix.
    Same approach as KUKA_Cube_CV_V4.py: raw gray + default DetectorParameters.
    Returns T_tag2cam (transforms points FROM tag frame TO camera frame).
    Returns None if tag not found.
    """
    from services.vision_service import get_aruco_dict

    aruco_dict = get_aruco_dict(aruco_dict_type)
    aruco_params = cv2.aruco.DetectorParameters()

    corners, ids, _ = cv2.aruco.detectMarkers(gray_image, aruco_dict, parameters=aruco_params)

    if ids is None:
        return None

    half = tag_size_mm / 2.0
    obj_pts = np.array([
        [-half,  half, 0],
        [ half,  half, 0],
        [ half, -half, 0],
        [-half, -half, 0]
    ], dtype=np.float32)

    for i, mid in enumerate(ids.flatten()):
        if mid != tag_id:
            continue

        img_pts = corners[i][0].astype(np.float32)
        ok, rvec, tvec = cv2.solvePnP(
            obj_pts, img_pts, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_IPPE_SQUARE
        )
        if not ok:
            return None

        R, _ = cv2.Rodrigues(rvec)
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = tvec.flatten()
        return T

    return None


def compute_hand_eye(robot_poses, camera_poses, method=cv2.CALIB_HAND_EYE_TSAI):
    """
    Compute hand-eye calibration (eye-in-hand) from paired robot/camera poses.

    Args:
        robot_poses: List of robot TCP poses as [X,Y,Z,A,B,C] (mm, degrees)
        camera_poses: List of 4x4 camera-to-target transforms (from ArUco/chessboard)
        method: cv2 hand-eye method (default TSAI)

    Returns:
        T_cam2flange as 4x4 numpy array
    """
    R_gripper2base = []
    t_gripper2base = []
    R_target2cam = []
    t_target2cam = []

    for robot_pose, cam_pose in zip(robot_poses, camera_poses):
        # Robot TCP to base
        T_tcp = kuka_abc_to_matrix(*robot_pose)
        R_gripper2base.append(T_tcp[:3, :3])
        t_gripper2base.append(T_tcp[:3, 3].reshape(3, 1))

        # Camera to target (invert: target-in-camera → camera-in-target not needed;
        # cv2.calibrateHandEye expects R_target2cam, t_target2cam)
        T_cam = np.array(cam_pose, dtype=np.float64)
        R_target2cam.append(T_cam[:3, :3])
        t_target2cam.append(T_cam[:3, 3].reshape(3, 1))

    R_cam2grip, t_cam2grip = cv2.calibrateHandEye(
        R_gripper2base, t_gripper2base,
        R_target2cam, t_target2cam,
        method=method
    )

    T_cam2flange = np.eye(4)
    T_cam2flange[:3, :3] = R_cam2grip
    T_cam2flange[:3, 3] = t_cam2grip.flatten()

    return T_cam2flange


class CalibrationEngine:
    """
    Core calibration engine. Computes $BASE correction from two-tag detection.

    Algorithm:
    1. Detect table tag (world ref) and part tag (workpiece) in camera frame
    2. Compute T_part2table_now = inv(T_table2cam) @ T_part2cam
    3. Compare with T_part2table_nominal (from teaching step)
    4. Compute correction in table-tag frame
    5. Transform correction to robot base frame using hand-eye + robot FK
    6. Apply correction to nominal $BASE
    """

    def __init__(self, camera_matrix, dist_coeffs, table_tag_id, part_tag_id,
                 tag_size_mm, hand_eye_matrix, nominal_part_tag_matrix,
                 nominal_base, max_correction_mm=50.0, max_correction_deg=5.0,
                 aruco_dict_type='DICT_6X6_250'):
        self.camera_matrix = np.array(camera_matrix, dtype=np.float64)
        self.dist_coeffs = np.array(dist_coeffs, dtype=np.float64).reshape(-1)
        self.table_tag_id = int(table_tag_id)
        self.part_tag_id = int(part_tag_id)
        self.tag_size_mm = float(tag_size_mm)
        self.max_correction_mm = float(max_correction_mm)
        self.max_correction_deg = float(max_correction_deg)
        self.aruco_dict_type = aruco_dict_type

        # Hand-eye: T_cam2flange (camera to flange/TCP)
        if hand_eye_matrix is not None:
            self.T_cam2flange = np.array(hand_eye_matrix, dtype=np.float64)
        else:
            self.T_cam2flange = None

        # Nominal part-to-table transform (from teaching step)
        if nominal_part_tag_matrix is not None:
            self.T_part2table_nominal = np.array(nominal_part_tag_matrix, dtype=np.float64)
        else:
            self.T_part2table_nominal = None

        # Nominal $BASE as [X, Y, Z, A, B, C]
        self.nominal_base = [float(v) for v in nominal_base]

    def detect_tags(self, gray_image):
        """Detect both table and part tags. Returns dict with poses."""
        T_table = detect_aruco_pose(
            gray_image, self.table_tag_id, self.tag_size_mm,
            self.camera_matrix, self.dist_coeffs, self.aruco_dict_type
        )
        T_part = detect_aruco_pose(
            gray_image, self.part_tag_id, self.tag_size_mm,
            self.camera_matrix, self.dist_coeffs, self.aruco_dict_type
        )
        return {
            'table_tag': T_table,
            'part_tag': T_part,
            'table_found': T_table is not None,
            'part_found': T_part is not None,
            'table_dist_mm': float(np.linalg.norm(T_table[:3, 3])) if T_table is not None else 0,
            'part_dist_mm': float(np.linalg.norm(T_part[:3, 3])) if T_part is not None else 0,
        }

    def teach_nominal(self, gray_image):
        """
        Capture the nominal part-to-table relationship.
        Call once with part at taught (reference) position.
        Returns T_part2table_nominal as 4x4 array.
        """
        result = self.detect_tags(gray_image)

        if result['table_tag'] is None:
            raise RuntimeError("Table reference tag not detected")
        if result['part_tag'] is None:
            raise RuntimeError("Part tag not detected")

        T_table2cam = result['table_tag']
        T_part2cam = result['part_tag']

        self.T_part2table_nominal = np.linalg.inv(T_table2cam) @ T_part2cam

        logger.info(f"Nominal part-to-table transform stored")
        return self.T_part2table_nominal

    def compute_correction(self, gray_image, robot_cart_pos):
        """
        Main calibration computation.

        Args:
            gray_image: Camera frame (grayscale)
            robot_cart_pos: Dict with X,Y,Z,A,B,C of robot TCP at capture position

        Returns dict with corrected_base, correction, poses.
        Raises RuntimeError on detection failure or excessive correction.
        """
        if self.T_part2table_nominal is None:
            raise RuntimeError("No nominal calibration. Run teach_nominal first.")
        if self.T_cam2flange is None:
            raise RuntimeError("No hand-eye calibration matrix loaded.")

        # Step 1: Detect tags
        result = self.detect_tags(gray_image)
        if result['table_tag'] is None:
            raise RuntimeError("Table reference tag not detected")
        if result['part_tag'] is None:
            raise RuntimeError("Part tag not detected")

        T_table2cam = result['table_tag']
        T_part2cam = result['part_tag']

        # Step 2: Current part-to-table relationship
        T_part2table_now = np.linalg.inv(T_table2cam) @ T_part2cam

        # Step 3: Correction in table-tag frame
        T_correction_table = T_part2table_now @ np.linalg.inv(self.T_part2table_nominal)

        # Step 4: Transform correction to robot base frame
        T_flange2base = kuka_abc_to_matrix(
            robot_cart_pos['X'], robot_cart_pos['Y'], robot_cart_pos['Z'],
            robot_cart_pos['A'], robot_cart_pos['B'], robot_cart_pos['C']
        )

        # Chain: table tag -> camera -> flange -> base
        T_table2base = T_flange2base @ self.T_cam2flange @ T_table2cam

        # Similarity transform: express correction in base frame
        T_correction_base = T_table2base @ T_correction_table @ np.linalg.inv(T_table2base)

        # Step 5: Apply correction to nominal base
        M_nominal = kuka_abc_to_matrix(*self.nominal_base)
        M_corrected = T_correction_base @ M_nominal
        corrected_xyzabc = matrix_to_kuka_abc(M_corrected)

        # Step 6: Compute delta
        correction = [
            corrected_xyzabc[i] - self.nominal_base[i] for i in range(6)
        ]

        # Step 7: Safety check
        trans_mag = np.sqrt(correction[0]**2 + correction[1]**2 + correction[2]**2)
        rot_mag = max(abs(correction[3]), abs(correction[4]), abs(correction[5]))

        if trans_mag > self.max_correction_mm:
            raise RuntimeError(
                f"Translation correction {trans_mag:.1f}mm exceeds limit "
                f"{self.max_correction_mm}mm. Part may be misplaced."
            )
        if rot_mag > self.max_correction_deg:
            raise RuntimeError(
                f"Rotation correction {rot_mag:.1f}deg exceeds limit "
                f"{self.max_correction_deg}deg. Part may be misoriented."
            )

        return {
            'corrected_base': list(corrected_xyzabc),
            'correction': correction,
            'table_tag_pose': T_table2cam.tolist(),
            'part_tag_pose': T_part2cam.tolist(),
            'translation_magnitude_mm': float(trans_mag),
            'rotation_magnitude_deg': float(rot_mag),
        }
