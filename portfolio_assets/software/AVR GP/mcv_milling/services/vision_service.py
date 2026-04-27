import cv2
import numpy as np
import base64
import threading
import logging

logger = logging.getLogger(__name__)

# Map setting string → OpenCV constant
ARUCO_DICT_MAP = {
    'DICT_4X4_50': cv2.aruco.DICT_4X4_50,
    'DICT_4X4_100': cv2.aruco.DICT_4X4_100,
    'DICT_4X4_250': cv2.aruco.DICT_4X4_250,
    'DICT_4X4_1000': cv2.aruco.DICT_4X4_1000,
    'DICT_5X5_50': cv2.aruco.DICT_5X5_50,
    'DICT_5X5_100': cv2.aruco.DICT_5X5_100,
    'DICT_5X5_250': cv2.aruco.DICT_5X5_250,
    'DICT_5X5_1000': cv2.aruco.DICT_5X5_1000,
    'DICT_6X6_50': cv2.aruco.DICT_6X6_50,
    'DICT_6X6_100': cv2.aruco.DICT_6X6_100,
    'DICT_6X6_250': cv2.aruco.DICT_6X6_250,
    'DICT_6X6_1000': cv2.aruco.DICT_6X6_1000,
    'DICT_7X7_50': cv2.aruco.DICT_7X7_50,
    'DICT_7X7_100': cv2.aruco.DICT_7X7_100,
    'DICT_7X7_250': cv2.aruco.DICT_7X7_250,
    'DICT_7X7_1000': cv2.aruco.DICT_7X7_1000,
}


def get_aruco_dict(dict_type='DICT_6X6_250'):
    """Return the cv2 ArUco dictionary for the given type string."""
    cv_id = ARUCO_DICT_MAP.get(dict_type, cv2.aruco.DICT_6X6_250)
    return cv2.aruco.getPredefinedDictionary(cv_id)


def _get_aruco_detector_params():
    """
    Default ArUco detector parameters — matching KUKA_Cube_CV_V4.py.
    The OpenCV defaults work best; over-tuning breaks bit decoding.
    """
    return cv2.aruco.DetectorParameters()


def preprocess_for_aruco(gray):
    """
    No preprocessing — pass raw grayscale to detectMarkers.
    The original KUKA_Cube_CV_V4.py works with raw gray and default params.
    """
    return gray


def auto_detect_aruco(gray):
    """
    Try all ArUco dictionaries on raw grayscale and return which ones detect markers.
    Returns list of (dict_name, corners, ids) for dictionaries that found markers.
    """
    params = _get_aruco_detector_params()
    results = []
    for dict_name, cv_id in ARUCO_DICT_MAP.items():
        aruco_dict = cv2.aruco.getPredefinedDictionary(cv_id)
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, aruco_dict, parameters=params
        )
        if ids is not None and len(ids) > 0:
            results.append((dict_name, corners, ids))
    return results


class VisionService:
    """Manages camera capture and provides frames for calibration and streaming."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._cap = None
                cls._instance._frame_lock = threading.Lock()
                cls._instance._latest_frame = None
            return cls._instance

    def open_camera(self, index=0, width=1280, height=720, fps=30):
        if self._cap is not None and self._cap.isOpened():
            return True
        self._cap = cv2.VideoCapture(index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera index {index}")
        for _ in range(5):
            self._cap.read()
        logger.info(f"Camera {index} opened at {width}x{height}")
        return True

    def close_camera(self):
        if self._cap:
            self._cap.release()
            self._cap = None

    @property
    def is_open(self):
        return self._cap is not None and self._cap.isOpened()

    def capture_frame(self):
        if self._cap is None or not self._cap.isOpened():
            raise RuntimeError("Camera not open")
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to capture frame")
        with self._frame_lock:
            self._latest_frame = frame.copy()
        return frame

    def capture_averaged(self, n=5):
        accum = None
        count = 0
        for _ in range(n):
            ret, frame = self._cap.read()
            if not ret:
                continue
            f = frame.astype(np.float32)
            accum = f if accum is None else accum + f
            count += 1
        if count == 0:
            raise RuntimeError("Failed to capture any frames")
        return (accum / count).astype(np.uint8)

    def get_latest_jpeg(self, quality=70):
        with self._frame_lock:
            if self._latest_frame is None:
                return b''
            _, buffer = cv2.imencode('.jpg', self._latest_frame,
                                      [cv2.IMWRITE_JPEG_QUALITY, quality])
            return buffer.tobytes()

    def draw_aruco_overlay(self, frame, camera_matrix, dist_coeffs, tag_size_mm,
                           aruco_dict_type='DICT_6X6_250'):
        """Same approach as KUKA_Cube_CV_V4.py: raw gray + default params."""
        display = frame.copy()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        aruco_dict = get_aruco_dict(aruco_dict_type)
        aruco_params = _get_aruco_detector_params()

        corners, ids, _ = cv2.aruco.detectMarkers(gray, aruco_dict, parameters=aruco_params)

        if ids is not None:
            cv2.aruco.drawDetectedMarkers(display, corners, ids)

            half = tag_size_mm / 2.0
            obj_pts = np.array([
                [-half, half, 0], [half, half, 0],
                [half, -half, 0], [-half, -half, 0]
            ], dtype=np.float32)

            for i, mid in enumerate(ids.flatten()):
                img_pts = corners[i][0].astype(np.float32)
                ok, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, camera_matrix, dist_coeffs,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE
                )
                if ok:
                    cv2.drawFrameAxes(display, camera_matrix, dist_coeffs,
                                      rvec, tvec, tag_size_mm * 0.5)
                    dist = np.linalg.norm(tvec)
                    center = tuple(corners[i][0].mean(axis=0).astype(int))
                    cv2.putText(display, f"ID:{mid} {dist:.0f}mm",
                                (center[0] - 40, center[1] - 20),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return display

    def get_segmentation_view(self, frame, camera_matrix, dist_coeffs, tag_size_mm,
                               table_tag_id=0, part_tag_id=1,
                               aruco_dict_type='DICT_6X6_250'):
        """
        Build a 2x2 diagnostic image:
          Top-left:  Raw grayscale
          Top-right: Adaptive threshold (what ArUco sees internally)
          Bot-left:  Detection with selected dict
          Bot-right: Auto-detect (tries ALL dictionaries)
        """
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Adaptive threshold — shows what ArUco's internal binarization sees
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY, 13, 7
        )

        aruco_params = _get_aruco_detector_params()

        # ── Bottom-left: detect with selected dictionary on raw gray ──
        aruco_dict = get_aruco_dict(aruco_dict_type)
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, aruco_dict, parameters=aruco_params
        )

        selected_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        if rejected:
            for rej in rejected:
                pts = rej[0].astype(np.int32)
                cv2.polylines(selected_overlay, [pts], True, (0, 0, 180), 1)
        n_selected = 0
        if ids is not None and len(ids) > 0:
            cv2.aruco.drawDetectedMarkers(selected_overlay, corners, ids)
            n_selected = len(ids)
            self._draw_pose_labels(selected_overlay, corners, ids, tag_size_mm,
                                    camera_matrix, dist_coeffs, table_tag_id, part_tag_id)

        # ── Bottom-right: auto-detect across ALL dictionaries on raw gray ──
        auto_overlay = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        auto_results = auto_detect_aruco(gray)
        auto_detected_dict = None
        auto_corners = None
        auto_ids = None
        if auto_results:
            auto_detected_dict, auto_corners, auto_ids = auto_results[0]
            cv2.aruco.drawDetectedMarkers(auto_overlay, auto_corners, auto_ids)
            self._draw_pose_labels(auto_overlay, auto_corners, auto_ids, tag_size_mm,
                                    camera_matrix, dist_coeffs, table_tag_id, part_tag_id)

        # Build detection info from whichever worked
        use_corners = corners if n_selected > 0 else auto_corners
        use_ids = ids if n_selected > 0 else auto_ids
        det_info = {
            'tags_found': [],
            'total_detected': n_selected if n_selected > 0 else (len(auto_ids) if auto_ids is not None else 0),
            'rejected_candidates': len(rejected) if rejected else 0,
            'aruco_dict': aruco_dict_type,
            'auto_detected_dict': auto_detected_dict if n_selected == 0 else None,
        }
        if use_ids is not None and use_corners is not None:
            half = tag_size_mm / 2.0
            obj_pts = np.array([
                [-half, half, 0], [half, half, 0],
                [half, -half, 0], [-half, -half, 0]
            ], dtype=np.float32)
            for i, mid in enumerate(use_ids.flatten()):
                tag_type = 'table' if mid == table_tag_id else (
                    'part' if mid == part_tag_id else 'unknown'
                )
                img_pts = use_corners[i][0].astype(np.float32)
                ok, rvec, tvec = cv2.solvePnP(
                    obj_pts, img_pts, camera_matrix, dist_coeffs,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE
                )
                dist_mm = float(np.linalg.norm(tvec)) if ok else 0
                det_info['tags_found'].append({
                    'id': int(mid), 'type': tag_type,
                    'distance_mm': round(dist_mm, 1),
                })

        # Convert panels to BGR
        gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)

        # Panel labels
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(gray_bgr, "RAW GRAYSCALE", (10, 25), font, 0.6, (0, 200, 255), 2)
        cv2.putText(thresh_bgr, "ADAPTIVE THRESHOLD", (10, 25), font, 0.6, (0, 200, 255), 2)
        cv2.putText(selected_overlay, f"SELECTED [{aruco_dict_type}] Found:{n_selected}",
                    (10, 25), font, 0.5, (0, 200, 255), 2)
        n_auto = len(auto_ids) if auto_ids is not None else 0
        auto_label = f"AUTO-DETECT Found:{n_auto}"
        if auto_detected_dict:
            auto_label += f" [{auto_detected_dict}]"
        cv2.putText(auto_overlay, auto_label, (10, 25), font, 0.5, (0, 255, 100), 2)

        # Compose 2x2 grid
        top = np.hstack([gray_bgr, thresh_bgr])
        bot = np.hstack([selected_overlay, auto_overlay])
        composite = np.vstack([top, bot])

        return composite, det_info

    def _draw_pose_labels(self, overlay, corners, ids, tag_size_mm,
                           camera_matrix, dist_coeffs, table_tag_id, part_tag_id):
        """Draw ID/type/distance labels and axes on an overlay image."""
        half = tag_size_mm / 2.0
        obj_pts = np.array([
            [-half, half, 0], [half, half, 0],
            [half, -half, 0], [-half, -half, 0]
        ], dtype=np.float32)

        for i, mid in enumerate(ids.flatten()):
            tag_type = 'table' if mid == table_tag_id else (
                'part' if mid == part_tag_id else 'unknown'
            )
            color = (0, 255, 0) if tag_type == 'table' else (
                (255, 200, 0) if tag_type == 'part' else (200, 200, 200)
            )
            img_pts = corners[i][0].astype(np.float32)
            ok, rvec, tvec = cv2.solvePnP(
                obj_pts, img_pts, camera_matrix, dist_coeffs,
                flags=cv2.SOLVEPNP_IPPE_SQUARE
            )
            if ok:
                dist_mm = float(np.linalg.norm(tvec))
                cv2.drawFrameAxes(overlay, camera_matrix, dist_coeffs,
                                  rvec, tvec, tag_size_mm * 0.5)
                center = tuple(corners[i][0].mean(axis=0).astype(int))
                cv2.putText(overlay, f"ID:{mid} [{tag_type}] {dist_mm:.0f}mm",
                            (center[0] - 60, center[1] - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    def find_chessboard(self, frame, rows, cols):
        """Detect chessboard corners in a frame. Returns (found, corners, annotated_frame)."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FAST_CHECK
        found, corners = cv2.findChessboardCorners(gray, (cols, rows), flags)
        display = frame.copy()
        if found:
            criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            cv2.drawChessboardCorners(display, (cols, rows), corners, found)
        return found, corners, display

    def compute_camera_calibration(self, all_corners, rows, cols, square_size_mm, image_size):
        """
        Compute camera calibration from collected chessboard corner sets.
        Returns dict with camera_matrix, dist_coeffs, rms, rvecs, tvecs.
        """
        obj_p = np.zeros((rows * cols, 3), np.float32)
        obj_p[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        obj_p *= square_size_mm

        obj_points = [obj_p for _ in all_corners]
        rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
            obj_points, all_corners, image_size, None, None
        )
        return {
            'camera_matrix': mtx,
            'dist_coeffs': dist,
            'rms': rms,
            'rvecs': rvecs,
            'tvecs': tvecs,
        }

    def get_segmentation_jpeg(self, frame, camera_matrix, dist_coeffs, tag_size_mm,
                               table_tag_id=0, part_tag_id=1,
                               aruco_dict_type='DICT_6X6_250', quality=80):
        """Get segmentation view as base64 JPEG string + detection info."""
        composite, det_info = self.get_segmentation_view(
            frame, camera_matrix, dist_coeffs, tag_size_mm,
            table_tag_id, part_tag_id, aruco_dict_type
        )
        _, buffer = cv2.imencode('.jpg', composite,
                                  [cv2.IMWRITE_JPEG_QUALITY, quality])
        b64 = base64.b64encode(buffer).decode('utf-8')
        return b64, det_info
