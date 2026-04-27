
import socket
from EkiUtils import EkiUtils
from CartesianPosition import CartesianPosition
from Frame import Frame
from LoadData import LoadData
from ProgramInfo import ProgramInfo
from Command import Command


class EkiManager:

    def __init__(self):
        self._socket = None
        self._utils = EkiUtils()
        self._cmd = Command()
        self._absAccureState = ""
        self._isOfficePc = False
        self._packet_callback = None

    def set_packet_callback(self, cb):
        """Set a callback fn(direction: str, data: str) for TX/RX logging."""
        self._packet_callback = cb

    def _notify(self, direction, data):
        """Fire packet callback if set. direction is 'TX' or 'RX'."""
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
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))

    def close(self):
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def getDataFromServer(self, cmd, split):
        if type(cmd) is bytes:
            self._notify("TX", cmd)
            self._socket.sendall(cmd)
        else:
            self._notify("TX", cmd)
            self._socket.sendall(cmd.encode('utf_8'))

        data = self._socket.recv(1024)
        self._notify("RX", data)
        if split:
            response = data.decode("utf-8").split(',')
        else:
            response = data.decode("utf-8")

        return response

    def getDataFromServerPos(self, cmd):
        if type(cmd) is bytes:
            self._notify("TX", cmd)
            self._socket.sendall(cmd)
        else:
            self._notify("TX", cmd)
            self._socket.sendall(cmd.encode('utf_8'))
        data = self._socket.recv(1024)
        self._notify("RX", data)

        pos = data.decode("utf-8").replace(";", "").split(',')

        posFltr = [item for item in pos if self._utils.is_float(item)]

        return posFltr

    def getResponse(self, cmd):
        self._notify("TX", cmd)
        self._socket.sendall(cmd)

        data = self._socket.recv(1024)
        self._notify("RX", data)

        recData = data.decode("utf-8").replace(";", "").split(',')

        fltrData = [item for item in recData if self._utils.is_float(item)]

        response = ','.join(fltrData)

        return response

    def getValue(self, data):
        return data[1].replace(";", "")

    def getCommand(self, info, cmd):
        data = [float(x) for x in info]

        data_formatted_list = ['%.4f' % elem for elem in data]

        dataStr = ','.join(str(e) for e in data_formatted_list)

        cmdVal = ','.join([cmd, dataStr]) + ';'

        return cmdVal

    def getRobotTypeFromKrc(self):
        robotTypeData = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_TYPE, True)

        response = robotTypeData[1][robotTypeData[1].index('#') + 1:robotTypeData[1].index('C4')]

        return response

    def getRobotNameFromKRC(self):
        robotNameData = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_NAME, True)

        return self.getValue(robotNameData)

    def getRobotSerialNumberFromKrc(self):
        snData = self.getDataFromServer(self._cmd.CMD_GET_ROBOT_SERIAL_NUM, True)

        return self.getValue(snData)

    def getSoftwareVersionFromKrc(self):
        svData = self.getDataFromServer(self._cmd.CMD_GET_SOFTWARE_VERSION, True)

        softwareVersionData = svData[1]

        if "office" in softwareVersionData.lower():
            self._isOfficePc = True
        else:
            self._isOfficePc = False

        response = svData[1][svData[1].index('V') + 1:svData[1].index('(')]

        return response

    def getNumRobotAxes(self):
        axesData = self.getDataFromServer(self._cmd.CMD_GET_NUM_ROBOT_AXES, True)

        return self.getValue(axesData)

    def getnumexternalaxes(self):
        externalAxesData = self.getDataFromServer(self._cmd.CMD_GET_EXTERNAL_AXES, True)

        return self.getValue(externalAxesData)

    def getOverride(self):
        ovrData = self.getDataFromServer(self._cmd.CMD_GET_OVERRIDE, True)

        return self.getValue(ovrData)

    def setHome(self, jointPos):
        posList = list.__add__(jointPos.get_robotAxes(), jointPos.get_externalAxes())

        cmdVal = self.getCommand(posList, self._cmd.CMD_SET_HOME)

        response = self.getDataFromServer(cmdVal, False)

        self.response(response)

    def getUpperJointLimits(self):
        response = self.getResponse(self._cmd.CMD_GET_POS_JNT_LIM)

        return response

    def getLowerJointLimits(self):
        response = self.getResponse(self._cmd.CMD_GET_NEG_JNT_LIM)

        return response

    def goToJointPos(self, jointPos):
        posList = list.__add__(jointPos.get_robotAxes(), jointPos.get_externalAxes())

        cmdVal = self.getCommand(posList, self._cmd.CMD_GO_TO_JOINT_POS)

        response = self.getDataFromServer(cmdVal, False)

        self.response(response)

    def isHome(self):
        data = self.getDataFromServer(self._cmd.CMD_IS_HOME, False)

        if data.lower().find("true") == -1:
            response = "False"
        else:
            response = "True"

        return response

    def response(self, resp):
        response = resp.lower()
        if response.find("success") == -1:
            raise Exception("Command failed: " + response)

    def setBaseData(self, basedata):
        cmdVal = self.getCommand(basedata, self._cmd.CMD_SET_BASE_DATA)

        response = self.getDataFromServer(cmdVal, False)

        self.response(response)

    def setToolData(self, tooldata):
        cmdVal = self.getCommand(tooldata, self._cmd.CMD_SET_TOOL_DATA)

        response = self.getDataFromServer(cmdVal, False)

        self.response(response)

    def getCurrentJointPos(self):
        currentJntLimitFilterd = self.getDataFromServerPos(self._cmd.CMD_GET_CURRENT_JOINTS)

        response = ("Robot axes: " + ','.join(currentJntLimitFilterd[0:6]) +
                    ", External Axes: " + ','.join(currentJntLimitFilterd[6:12]))

        return response

    def getCurrentCartPos(self):
        currentPosFltr = self.getDataFromServerPos(self._cmd.CMD_GET_CURRENT_POS)

        response = CartesianPosition(
            Frame(currentPosFltr[0:6]),
            currentPosFltr[6],
            currentPosFltr[7],
            currentPosFltr[8:len(currentPosFltr)]
        )

        return response

    def goToCartesianPos(self, crtPos):
        data = [float(i) for i in crtPos]

        dataStr = ','.join(str(e) for e in data)

        cmdVal = ','.join([self._cmd.CMD_GO_TO_CART_POS, dataStr]) + ';'

        self._notify("TX", cmdVal)
        self._socket.sendall(cmdVal.encode('utf_8'))

        rx = self._socket.recv(1024)
        self._notify("RX", rx)
        response = rx.decode("utf-8").lower()

        if response.find("success") == -1:
            raise Exception("Command failed: " + response)

    def goToFrame(self, frame):
        cmdVal = self.getCommand(frame, self._cmd.CMD_GO_TO_FRAME)

        response = self.getDataFromServer(cmdVal, False)

        self.response(response)

    def getBaseData(self):
        response = self.getResponse(self._cmd.CMD_GET_BASE_DATA)

        return response

    def getToolData(self):
        response = self.getResponse(self._cmd.CMD_GET_TOOL_DATA)
        return response

    def getLoadData(self):
        self._notify("TX", self._cmd.CMD_GET_LOAD_DATA)
        self._socket.sendall(self._cmd.CMD_GET_LOAD_DATA)

        data = self._socket.recv(1024)
        self._notify("RX", data)

        recData = data.decode("utf-8").replace(";", "").split(',')
        recDataFltr = [item for item in recData if self._utils.is_float(item)]

        loadData = LoadData(recDataFltr[0], recDataFltr[1:7], recDataFltr[7:10])

        return str(loadData)

    def getabsaccurstatus(self):
        self._notify("TX", self._cmd.CMD_GET_ABS_ACCUR_STATUS)
        self._socket.sendall(self._cmd.CMD_GET_ABS_ACCUR_STATUS)
        data = self._socket.recv(1024)
        self._notify("RX", data)
        absData = data.decode("utf-8").split(',')
        self._absAccureState = absData[1].replace(";", "")
        return self._absAccureState

    def isAbsoluteAccurate(self):
        return str(self._absAccureState.lower() != "none")

    def isAbsoluteAccuracyActive(self):
        return str(self._absAccureState.lower() == "active")

    def isPidFilePresent(self):
        return str(self._absAccureState.lower() != "none")

    def getOperatingMode(self):
        self._notify("TX", self._cmd.CMD_GET_OPERATING_MODE)
        self._socket.sendall(self._cmd.CMD_GET_OPERATING_MODE)
        data = self._socket.recv(1024)
        self._notify("RX", data)
        mode = data.decode("utf-8").split(',')
        response = mode[1].replace(";", "")

        return response

    def isOfficePc(self):
        return self._isOfficePc

    def getProgrmaInfo(self):
        prgInfo = ProgramInfo()

        self._notify("TX", self._cmd.CMD_GET_PROGRAM_INFO)
        self._socket.sendall(self._cmd.CMD_GET_PROGRAM_INFO)
        data = self._socket.recv(1024)
        self._notify("RX", data)

        info = data.decode("utf-8").split(",")

        prgInfo.set_programName(info[1])
        prgInfo.set_programState(info[2].replace(";", ""))

        return str(prgInfo)

    def setCartSpeed(self, speed_m_per_s):
        """Set linear (Cartesian) speed in m/s. Range: 0.0 to $VEL_MA.CP."""
        cmdVal = self.getCommand([speed_m_per_s], self._cmd.CMD_SET_CART_SPEED)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setJointSpeed(self, speed_pct):
        """Set joint speed as percentage. Range: 0.0 to 100.0."""
        cmdVal = self.getCommand([speed_pct], self._cmd.CMD_SET_JOINT_SPEED)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setCartAccel(self, accel):
        """Set linear (Cartesian) acceleration. Range: 0.0 to $ACC_MA.CP."""
        cmdVal = self.getCommand([accel], self._cmd.CMD_SET_CART_ACCEL)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def setJointAccel(self, accel_pct):
        """Set joint acceleration as percentage. Range: 0.0 to 100.0."""
        cmdVal = self.getCommand([accel_pct], self._cmd.CMD_SET_JOINT_ACCEL)
        response = self.getDataFromServer(cmdVal, False)
        self.response(response)

    def gripOpen(self):
        response = self.getDataFromServer(self._cmd.CMD_GRIP_OPEN, False)
        self.response(response)

    def gripClose(self):
        response = self.getDataFromServer(self._cmd.CMD_GRIP_CLOSE, False)
        self.response(response)
