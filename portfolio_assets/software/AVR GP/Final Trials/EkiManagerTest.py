# echo-client.py


from EkiManager import EkiManager
from JointPosition import JointPosition
import random
from Frame import Frame
def main():
    host = "192.168.1.1"  # The server's hostname or IP address
    port = 54610  # The port used by the server
    
    ekiManager = EkiManager()
    ekiManager.connect(host,port)

    homePos = JointPosition([0, -90, 90, 0, 90, 0],[0,0,0,0,0,0,])

    print("Program state: " + ekiManager.getProgrmaInfo())

    print("Robot Type:"+ ekiManager.getRobotTypeFromKrc())

    print("Robot Name:"+ ekiManager.getRobotNameFromKRC())

    print("Robot SN:" + ekiManager.getRobotSerialNumberFromKrc())

    print("SW Version:" + ekiManager.getSoftwareVersionFromKrc())

    print("Num Robot Axes:" + ekiManager.getNumRobotAxes())

    print("Num external axes:" + ekiManager.getnumexternalaxes())

    print("Is officePC?: " +str(ekiManager.isOfficePc()))

    print( "Override: " + ekiManager.getOverride())

    print ("Upper Jnt Lim: " + ekiManager.getUpperJointLimits())

    print ("Lower Jnt Lim: " + ekiManager.getLowerJointLimits())

    ekiManager.setHome(homePos)

    ekiManager.goToJointPos(homePos)

    print("Robot at home: "+ekiManager.isHome())

    ekiManager.setBaseData(random.sample(range(100), 6))

    ekiManager.setToolData(random.sample(range(100), 6))

    ekiManager.goToJointPos(JointPosition([-90, -50, 125, -100, -90, 100],[ 0, 0, 0, 0, 0, 0]))

    print("Joint Pos: " + ekiManager.getCurrentJointPos())

    cartPos = ekiManager.getCurrentCartPos()

    print("Cart Pos: " + str(cartPos))

    cartPos.set_frame([1270, 500, 450, -150, 10, -80])

    ekiManager.goToCartesianPos(cartPos.asArray())

    ekiManager.goToFrame([1271, 501, 451, -151, 11, -81])

    print("Base Data :"+ekiManager.getBaseData())

    print("Tool Data :"+ekiManager.getToolData())

    print("Load Data"+ekiManager.getLoadData())

    print("Abs Accur state: " +ekiManager.getabsaccurstatus())

    print("Abs Accur: " + ekiManager.isAbsoluteAccurate())

    print("Abs Accur active: " + ekiManager.isAbsoluteAccuracyActive())

    print("PID file present: " + ekiManager.isPidFilePresent())

    print("Operating mode: "  + ekiManager.getOperatingMode())

if __name__=="__main__":
    main()





