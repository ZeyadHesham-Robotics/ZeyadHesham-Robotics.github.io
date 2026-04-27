import socket
import threading
import logging

from .eki_utils import EkiUtils
from .cartesian_position import CartesianPosition
from .frame import Frame
from .joint_position import JointPosition
from .command import Command

logger = logging.getLogger(__name__)


class EkiManager:

    def __init__(self):
        self._socket = None
        self._utils = EkiUtils()
        self._cmd = Command()
        self._absAccureState = ""
        self._isOfficePc = False
        self._packet_callback = None
        self._lock = threading.Lock()

    @property
    def is_connected(self):
        return self._socket is not None

    def set_packet_callback(self, cb):
        self._packet_callback = cb

    def _notify(self, direction, data):
        if self._packet_callback is not None:
            try:
                if isinstance(data, bytes):
                    text = data.decode("utf-8", errors="replace")
                else:
                    text = str(data)
                self._packet_callback(direction, text)
            except Exception:
                pass

    def connect(self, host, port):
        with self._lock:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(10.0)
            self._socket.connect((host, port))
            logger.info(f"Connected to robot at {host}:{port}")

    def disconnect(self):
        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
                logger.info("Disconnected from robot")

    def close(self):
        self.disconnect()

    def _send_recv(self, cmd):
        """Thread-safe send + recv. Returns raw bytes response."""
        with self._lock:
            if self._socket is None:
                raise ConnectionError("Not connected to robot")
            if isinstance(cmd, bytes):
                self._notify("TX", cmd)
                self._socket.sendall(cmd)
            else:
                self._notify("TX", cmd)
                self._socket.sendall(cmd.encode('utf_8'))
            data = self._socket.recv(1024)
            self._notify("RX", data)
            return data

    def getDataFromServer(self, cmd, split):
        data = self._send_recv(cmd)
        if split:
            return data.decode("utf-8").split(',')
        return data.decode("utf-8")

    def getDataFromServerPos(self, cmd):
        data = self._send_recv(cmd)
        pos = data.decode("utf-8").replace(";", "").split(',')
        return [item for item in pos if self._utils.is_float(item)]

    def getResponse(self, cmd):
        data = self._send_recv(cmd)
        recData = data.decode("utf-8").replace(";", "").split(',')
        fltrData = [item for item in recData if self._utils.is_float(item)]
        return ','.join(fltrData)

    def getValue(self, data):
        return data[1].replace(";", "")

    def getCommand(self, info, cmd):
        data = [float(x) for x in info]
        data_formatted_list = ['%.4f' % elem for elem in data]
        dataStr = ','.join(str(e) for e in data_formatted_list)
        return ','.join([cmd, dataStr]) + ';'

    def response(self, resp):
        response = resp.lower()
        if response.find("success") == -1:
            raise Exception("Command failed: " + response)

    # ── Robot info queries ────────────────────────────────────

    def getRobotTypeFromKrc(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_TYPE, True)
        return data[1][data[1].index('#') + 1:data[1].index('C4')]

    def getRobotNameFromKRC(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_NAME, True)
        return self.getValue(data)

    def getRobotSerialNumberFromKrc(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_SERIAL_NUM, True)
        return self.getValue(data)

    def getSoftwareVersionFromKrc(self):
        svData = self.getDataFromServer(self._cmd.CMD_GET_SOFTWARE_VERSION, True)
        softwareVersionData = svData[1]
        self._isOfficePc = "office" in softwareVersionData.lower()
        return svData[1][svData[1].index('V') + 1:svData[1].index('(')]

    def getNumRobotAxes(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_NUM_ROBOT_AXES, True)
        return self.getValue(data)

    def getnumexternalaxes(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_EXTERNAL_AXES, True)
        return self.getValue(data)

    def getOverride(self):
        data = self.getDataFromServer(self._cmd.CMD_GET_OVERRIDE, True)
        return self.getValue(data)

    def getOperatingMode(self):
        data = self._send_recv(self._cmd.CMD_GET_OPERATING_MODE)
        mode = data.decode("utf-8").split(',')
        return mode[1].replace(";", "")

    def isHome(self):
        data = self.getDataFromServer(self._cmd.CMD_IS_HOME, False)
        return "true" in data.lower()

    def getProgrmaInfo(self):
        data = self._send_recv(self._cmd.CMD_GET_PROGRAM_INFO)
        info = data.decode("utf-8").split(",")
        return {'name': info[1] if len(info) > 1 else 'unknown',
                'state': info[2].replace(";", "") if len(info) > 2 else 'unknown'}

    # ── Position queries ──────────────────────────────────────

    def getCurrentCartPos(self):
        posFltr = self.getDataFromServerPos(self._cmd.CMD_GET_CURRENT_POS)
        return CartesianPosition(
            Frame([float(v) for v in posFltr[0:6]]),
            posFltr[6] if len(posFltr) > 6 else None,
            posFltr[7] if len(posFltr) > 7 else None,
            posFltr[8:] if len(posFltr) > 8 else []
        )

    def getCurrentJointPos(self):
        posFltr = self.getDataFromServerPos(self._cmd.CMD_GET_CURRENT_JOINTS)
        robot_axes = [float(v) for v in posFltr[0:6]] if len(posFltr) >= 6 else [0.0] * 6
        ext_axes = [float(v) for v in posFltr[6:12]] if len(posFltr) >= 12 else [0.0] * 6
        return JointPosition(robot_axes, ext_axes)

    # ── Motion commands ───────────────────────────────────────

    def goToJointPos(self, jointPos):
        posList = list.__add__(jointPos.get_robotAxes(), jointPos.get_externalAxes())
        cmdVal = self.getCommand(posList, self._cmd.CMD_GO_TO_JOINT_POS)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def goToFrame(self, frame):
        cmdVal = self.getCommand(frame, self._cmd.CMD_GO_TO_FRAME)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def goToCartesianPos(self, crtPos):
        data = [float(i) for i in crtPos]
        dataStr = ','.join(str(e) for e in data)
        cmdVal = ','.join([self._cmd.CMD_GO_TO_CART_POS, dataStr]) + ';'
        raw = self._send_recv(cmdVal)
        response = raw.decode("utf-8").lower()
        if response.find("success") == -1:
            raise Exception("Command failed: " + response)

    # ── Configuration commands ────────────────────────────────

    def setBaseData(self, basedata):
        cmdVal = self.getCommand(basedata, self._cmd.CMD_SET_BASE_DATA)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setToolData(self, tooldata):
        cmdVal = self.getCommand(tooldata, self._cmd.CMD_SET_TOOL_DATA)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setHome(self, jointPos):
        posList = list.__add__(jointPos.get_robotAxes(), jointPos.get_externalAxes())
        cmdVal = self.getCommand(posList, self._cmd.CMD_SET_HOME)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def getBaseData(self):
        return self.getResponse(self._cmd.CMD_GET_BASE_DATA)

    def getToolData(self):
        return self.getResponse(self._cmd.CMD_GET_TOOL_DATA)

    # ── Speed / acceleration ──────────────────────────────────

    def setCartSpeed(self, speed_m_per_s):
        cmdVal = self.getCommand([speed_m_per_s], self._cmd.CMD_SET_CART_SPEED)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setJointSpeed(self, speed_pct):
        cmdVal = self.getCommand([speed_pct], self._cmd.CMD_SET_JOINT_SPEED)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setCartAccel(self, accel):
        cmdVal = self.getCommand([accel], self._cmd.CMD_SET_CART_ACCEL)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setJointAccel(self, accel_pct):
        cmdVal = self.getCommand([accel_pct], self._cmd.CMD_SET_JOINT_ACCEL)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    # ── Gripper ───────────────────────────────────────────────

    def gripOpen(self):
        response = self.getDataFromServer(self._cmd.CMD_GRIP_OPEN, False)
        self.response(response)

    def gripClose(self):
        response = self.getDataFromServer(self._cmd.CMD_GRIP_CLOSE, False)
        self.response(response)

    # ── Misc ──────────────────────────────────────────────────

    def getUpperJointLimits(self):
        return self.getResponse(self._cmd.CMD_GET_POS_JNT_LIM)

    def getLowerJointLimits(self):
        return self.getResponse(self._cmd.CMD_GET_NEG_JNT_LIM)

    def isOfficePc(self):
        return self._isOfficePc
