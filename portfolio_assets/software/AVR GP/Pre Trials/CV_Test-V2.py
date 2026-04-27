import cv2
import numpy as np

# =========================
# Camera selection (External)
# =========================
EXTERNAL_CAMERA_INDEX = 1
AUTO_DETECT = True
BACKEND = cv2.CAP_MSMF

def list_working_cameras(max_index=8):
    working = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, BACKEND)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                working.append(i)
        cap.release()
    return working

if AUTO_DETECT:
    cams = list_working_cameras(8)
    if not cams:
        print("❌ No camera found. Close Zoom/Teams/Chrome and try again.")
        raise SystemExit
    print("✅ Cameras indexes:", cams)
    cam_index = EXTERNAL_CAMERA_INDEX if EXTERNAL_CAMERA_INDEX in cams else cams[0]
else:
    cam_index = EXTERNAL_CAMERA_INDEX

cap = cv2.VideoCapture(cam_index, BACKEND)
if not cap.isOpened():
    print("❌ Cannot open camera index:", cam_index)
    raise SystemExit

# Set resolution (affects intrinsics if you calibrated at different res!)
W, H = 640, 480
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

# =========================
# ORANGE segmentation
# =========================
lower_orange = np.array([5, 110, 110])
upper_orange = np.array([22, 255, 255])
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))

# =========================
# 3D parameters (YOU MUST SET THESE)
# =========================
# 1) Real cube size (meters). Example: 5cm cube -> 0.05
CUBE_SIZE_M = 0.05

# 2) Camera intrinsics (pixels)
# If you don't have calibration:
# - Use the "Quick calibration" method below to estimate FX (and set FY=FX).
FX = 800.0
FY = 800.0

# Principal point (usually image center for a quick setup)
CX0 = W / 2.0
CY0 = H / 2.0

def estimate_xyz_from_center_and_size(cx, cy, pixel_size):
    """
    Approx depth using pinhole camera model:
      Z = fx * real_size / pixel_size
      X = (cx - cx0) * Z / fx
      Y = (cy - cy0) * Z / fy
    Returns meters in camera coordinates.
    """
    if pixel_size <= 1:
        return None

    Z = (FX * CUBE_SIZE_M) / float(pixel_size)
    X = ( (cx - CX0) * Z ) / FX
    Y = ( (cy - CY0) * Z ) / FY
    return (X, Y, Z)

print("✅ Running. Press q/Esc to exit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    blurred = cv2.GaussianBlur(frame, (7, 7), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    mask = cv2.inRange(hsv, lower_orange, upper_orange)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    xyz = None

    if contours:
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)

        if area > 1500:
            # Rotated box (follows rotation)
            rect = cv2.minAreaRect(c)              # ((cx,cy),(rw,rh),angle)
            (cx, cy), (rw, rh), angle = rect

            # ✅ Red tracking point = EXACT center of the box
            cx_i, cy_i = int(cx), int(cy)
            cv2.circle(frame, (cx_i, cy_i), 8, (0, 0, 255), -1)

            # Draw rotated box
            box = cv2.boxPoints(rect)
            box = np.intp(box)
            cv2.drawContours(frame, [box], 0, (0, 255, 0), 2)

            # Use a stable pixel size for depth:
            # since it's a cube, take the larger side in pixels
            pixel_size = max(rw, rh)

            xyz = estimate_xyz_from_center_and_size(cx, cy, pixel_size)

            # Show 2D info
            cv2.putText(frame, f"Center(px): ({cx_i},{cy_i}) angle:{angle:.1f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            # Show 3D info if available
            if xyz is not None:
                X, Y, Z = xyz
                cv2.putText(frame, f"XYZ(m): X={X:.3f}  Y={Y:.3f}  Z={Z:.3f}",
                            (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                # Also print to terminal (optional)
                # print(f"XYZ(m): {X:.4f}, {Y:.4f}, {Z:.4f}")

    cv2.imshow("Orange Cube Tracking (Center + XYZ)", frame)
    cv2.imshow("Mask", mask)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == 27:
        break

cap.release()
cv2.destroyAllWindows()