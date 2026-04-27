from EkiManager import EkiManager
from JointPosition import JointPosition

# ================= ROBOT CONNECTION =================
host = "192.168.1.1"
port = 54610
ekiManager = EkiManager()
ekiManager.connect(host, port)  # Connect to robot

# ================= HOME POSITION =================
homePos = JointPosition([0, -90, 90, 0, 90, -90], [0]*6)

# Go home first (optional)
ekiManager.goToJointPos(homePos)

# ================= MOVE TO CARTESIAN =================
# Assume you receive these from another code
X, Y, Z, A, B, C = 1200, 0, 800, 0, 0, 0  # Replace with your values

cartPos = ekiManager.getCurrentCartPos()  # Get current Cartesian frame
cartPos.set_frame([X, Y, Z, A, B, C])
ekiManager.goToCartesianPos(cartPos.asArray())  # Move robot
print(f"✅ Robot moved to XYZABC = [{X}, {Y}, {Z}, {A}, {B}, {C}]")

# ================= OPTIONAL: RETURN HOME =================
ekiManager.goToJointPos(homePos)
print("🏠 Robot returned home.")