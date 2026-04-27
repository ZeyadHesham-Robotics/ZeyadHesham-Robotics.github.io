
import socket
from unicodedata import numeric
from EkiUtils import EkiUtils
from CartesianPosition import CartesianPosition
from Frame import Frame
from LoadData import LoadData
from ProgramInfo import ProgramInfo
from Command import Command

class EkiManager:
    global utils,command
    useCommandId = False
    absAccureState = ""
    isOfficePc=False

    utils = EkiUtils()

    command = Command()
    
    
   
    def connect(self,host,port):
        global s
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        s.connect((host, port))

    def getDataFromServer(self,cmd,split):
        global useCommandId , s

        if type(cmd) is bytes :
            s.sendall(cmd)
        else:
            s.sendall(cmd.encode('utf_8'))
        
        data = s.recv(1024)
        if(split == True):
            response = data.decode("utf-8").split(',')
        else:
            response = data.decode("utf-8")

        return response

    def getDataFromServerPos(self,cmd):
        global useCommandId , s

        if type(cmd) is bytes :
            s.sendall(cmd)
        else:
            s.sendall(cmd.encode('utf_8'))
        data = s.recv(1024)

        pos = data.decode("utf-8").replace(";", "").split(',')
               
        posFltr = [data for data in pos if  utils.is_float(data)]

        return posFltr

    def getResponse(self,cmd):
        global useCommandId , s

        s.sendall(cmd)

        data = s.recv(1024)

        recData = data.decode("utf-8").replace(";", "").split(',')
        
        fltrData = [data for data in recData if  utils.is_float(data)]

        response = ','.join(fltrData)

        return response

    def getValue(self,data):
        return data[1].replace(";","")

    def getCommand(self,info,cmd):
        data = [float(x) for x in info]

        data_formatted_list = [ '%.4f' % elem for elem in data ]

        dataStr = ','.join(str(e) for e in data_formatted_list)

        cmdVal = ','.join([cmd,dataStr])+';'

        return cmdVal

    def getRobotTypeFromKrc(self):

        robotTypeData = self.getDataFromServer(command.CMD_GET_ROBOT_TYPE,True)
         
        response = robotTypeData[1][robotTypeData[1].index('#')+1:robotTypeData[1].index('C4')]
              
        return response

    def getRobotNameFromKRC(self):
        
        robotNameData = self.getDataFromServer(command.CMD_GET_ROBOT_NAME,True)
               
        return self.getValue(robotNameData)

    def getRobotSerialNumberFromKrc(self):
       
        snData = self.getDataFromServer(command.CMD_GET_ROBOT_SERIAL_NUM,True)
        
        return self.getValue(snData)


    def getSoftwareVersionFromKrc(self):
        global isOfficePc

        svData = self.getDataFromServer(command.CMD_GET_SOFTWARE_VERSION,True)

        softwareVersionData = svData[1]
        
        if "office" in softwareVersionData.lower():
            isOfficePc = True
        else:
            isOfficePc = False
            
        response = svData[1][svData[1].index('V')+1:svData[1].index('(')]
        
        return response

    def getNumRobotAxes(self):

        axesData =  self.getDataFromServer(command.CMD_GET_NUM_ROBOT_AXES,True)
        
        return self.getValue(axesData)
    
    def getnumexternalaxes(self):
       
        externalAxesData = self.getDataFromServer(command.CMD_GET_EXTERNAL_AXES,True)

        return self.getValue(externalAxesData)

    def getOverride(self):

        ovrData = self.getDataFromServer(command.CMD_GET_OVERRIDE,True)

        return self.getValue(ovrData)

    def setHome(self,jointPos):

        posList = list.__add__(jointPos.get_robotAxes(),jointPos.get_externalAxes())
        
        cmdVal = self.getCommand(posList,command.CMD_SET_HOME)
       
        response = self.getDataFromServer(cmdVal,False)

        self.response(response)
        
    def getUpperJointLimits(self):

        response = self.getResponse(command.CMD_GET_POS_JNT_LIM)

        return response

    def getLowerJointLimits(self):

        response = self.getResponse(command.CMD_GET_NEG_JNT_LIM)

        return response
        
    def goToJointPos(self,jointPos):

       
        posList = list.__add__(jointPos.get_robotAxes(),jointPos.get_externalAxes())
       
        cmdVal = self.getCommand(posList,command.CMD_GO_TO_JOINT_POS)

        response = self.getDataFromServer(cmdVal,False)

        self.response(response)

    
    def isHome(self):
        
        data = self.getDataFromServer(command.CMD_IS_HOME,False)

        if data.lower().find("true") == -1:
            response = "False"
        else:
            response = "True" 

        return response

    def response(self,resp):
        response  = resp.lower()
        if response.find("success") == -1:
           raise Exception("Command failed: " + response)

    def setBaseData(self,basedata):
        basedata = basedata
        cmdVal = self.getCommand(basedata,command.CMD_SET_BASE_DATA)

        response = self.getDataFromServer(cmdVal,False)

        self.response(response)
        
        
    
    def setToolData(self,tooldata):
        toolData = tooldata
        cmdVal = self.getCommand(toolData,command.CMD_SET_TOOL_DATA)
        
        response = self.getDataFromServer(cmdVal,False)
        
        self.response(response)

    def getCurrentJointPos(self):
       
        currentJntLimitFilterd = self.getDataFromServerPos(command.CMD_GET_CURRENT_JOINTS)
        
        response = "Robot axes: "+','.join(currentJntLimitFilterd[0:6])+ ", External Axes: "+','.join(currentJntLimitFilterd[6:12])

        return response

    def getCurrentCartPos(self):
       
        currentPosFltr = self.getDataFromServerPos(command.CMD_GET_CURRENT_POS)
               
        response = CartesianPosition(Frame(currentPosFltr[0:6]),currentPosFltr[6],currentPosFltr[7],currentPosFltr[8:len(currentPosFltr)])

        return response
   
    def goToCartesianPos(self,crtPos):
        global useCommandId , s
        
        data = [float(i) for i in crtPos]

        dataStr = ','.join(str(e) for e in data)

        cmdVal = ','.join([command.CMD_GO_TO_CART_POS,dataStr])+';'

        s.sendall(cmdVal.encode('utf_8'))

        response = s.recv(1024).decode("utf-8").lower()
        
        if response.find("success") == -1:
           raise Exception("Command failed: " + response)



    def goToFrame(self,frame):

        cmdVal = self.getCommand(frame,command.CMD_GO_TO_FRAME)
        
        response = self.getDataFromServer(cmdVal,False)

        self.response(response)
        
        

    def getBaseData(self):
        response =  self.getResponse(command.CMD_GET_BASE_DATA)
       
        return response

    def getToolData(self):
        response =  self.getResponse(command.CMD_GET_TOOL_DATA)
        return response

        

    def getLoadData(self):
        global useCommandId , s

        s.sendall(command.CMD_GET_LOAD_DATA)

        data = s.recv(1024)

        recData = data.decode("utf-8").replace(";", "").split(',')
        recDataFltr = [data for data in recData if  utils.is_float(data)]

        loadData = LoadData(recDataFltr[0],recDataFltr[1:7],recDataFltr[7:10])
        
        return str(loadData)        

    def getabsaccurstatus(self):
        global useCommandId , s ,absAccureState

        s.sendall(command.CMD_GET_ABS_ACCUR_STATUS)
        data = s.recv(1024)
        absData = data.decode("utf-8").split(',')
        absAccureState = absData[1].replace(";","")
        return absAccureState

    def isAbsoluteAccurate(self):
        return str(absAccureState.lower() != "none")

    def isAbsoluteAccuracyActive(self):
        return str(absAccureState.lower() == "active")
    
    def isPidFilePresent(self):
        return str(absAccureState.lower() != "none")

    def getOperatingMode(self):
        global useCommandId , s

        s.sendall(command.CMD_GET_OPERATING_MODE)
        data = s.recv(1024)
        mode = data.decode("utf-8").split(',')
        response = mode[1].replace(";","")
        
        return response 
              
    def isOfficePc(self):
        global isOfficePc
        return isOfficePc

    def getProgrmaInfo(self):
        global useCommandId , s

        prgInfo = ProgramInfo()

        s.sendall(command.CMD_GET_PROGRAM_INFO)
        data = s.recv(1024)

        info = data.decode("utf-8").split(",")

        prgInfo.set_programName(info[1])
        prgInfo.set_programState(info[2].replace(";",""))
        

        return str(prgInfo)

        






