import threading
import logging
import sys
import os

# Add parent dir to path so we can import robot package
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot.eki_manager import EkiManager
from robot.joint_position import JointPosition

logger = logging.getLogger(__name__)


class RobotService:
    """Thread-safe singleton that manages the robot connection."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._eki = EkiManager()
                cls._instance._connected = False
                cls._instance._robot_ip = None
                cls._instance._robot_port = None
            return cls._instance

    @property
    def is_connected(self):
        return self._connected

    @property
    def eki(self):
        return self._eki

    def connect(self, ip, port):
        try:
            self._eki.connect(ip, int(port))
            self._connected = True
            self._robot_ip = ip
            self._robot_port = port
            try:
                robot_name = self._eki.getRobotNameFromKRC()
            except Exception:
                robot_name = "Unknown"
            return {'status': 'connected', 'robot_name': robot_name}
        except Exception as e:
            self._connected = False
            return {'status': 'error', 'message': str(e)}

    def disconnect(self):
        self._eki.disconnect()
        self._connected = False
        return {'status': 'disconnected'}

    def get_current_cart_pos(self):
        self._require_connection()
        pos = self._eki.getCurrentCartPos()
        f = pos.frame
        return {
            'X': float(f.x), 'Y': float(f.y), 'Z': float(f.z),
            'A': float(f.a), 'B': float(f.b), 'C': float(f.c),
            'status': pos.status, 'turn': pos.turn
        }

    def get_current_joint_pos(self):
        self._require_connection()
        jp = self._eki.getCurrentJointPos()
        ra = jp.get_robotAxes()
        ea = jp.get_externalAxes()
        return {
            'A1': float(ra[0]), 'A2': float(ra[1]),
            'A3': float(ra[2]), 'A4': float(ra[3]),
            'A5': float(ra[4]), 'A6': float(ra[5]),
            'E1': float(ea[0]), 'E2': float(ea[1]),
            'E3': float(ea[2]), 'E4': float(ea[3]),
            'E5': float(ea[4]), 'E6': float(ea[5]),
        }

    def set_base_data(self, x, y, z, a, b, c):
        self._require_connection()
        base_list = [float(x), float(y), float(z), float(a), float(b), float(c)]
        self._eki.setBaseData(base_list)
        logger.info(f"Base data set: X={x:.3f} Y={y:.3f} Z={z:.3f} A={a:.3f} B={b:.3f} C={c:.3f}")

    def get_base_data(self):
        self._require_connection()
        return self._eki.getBaseData()

    def go_to_joint_pos(self, joint_angles):
        self._require_connection()
        robot_axes = [float(a) for a in joint_angles[:6]]
        ext_axes = [float(a) for a in joint_angles[6:12]]
        jp = JointPosition(robot_axes, ext_axes)
        self._eki.goToJointPos(jp)

    def go_to_frame(self, frame_list):
        self._require_connection()
        self._eki.goToFrame([float(v) for v in frame_list])

    def get_robot_info(self):
        self._require_connection()
        info = {}
        try:
            info['name'] = self._eki.getRobotNameFromKRC()
        except Exception:
            info['name'] = 'Unknown'
        try:
            info['type'] = self._eki.getRobotTypeFromKrc()
        except Exception:
            info['type'] = 'Unknown'
        try:
            info['override'] = self._eki.getOverride()
        except Exception:
            info['override'] = '--'
        try:
            info['operating_mode'] = self._eki.getOperatingMode()
        except Exception:
            info['operating_mode'] = 'Unknown'
        try:
            info['is_home'] = self._eki.isHome()
        except Exception:
            info['is_home'] = False
        try:
            info['program_info'] = self._eki.getProgrmaInfo()
        except Exception:
            info['program_info'] = {}
        return info

    def set_cart_speed(self, speed):
        self._require_connection()
        self._eki.setCartSpeed(float(speed))

    def set_joint_speed(self, speed):
        self._require_connection()
        self._eki.setJointSpeed(float(speed))

    def _require_connection(self):
        if not self._connected:
            raise ConnectionError("Robot not connected")
