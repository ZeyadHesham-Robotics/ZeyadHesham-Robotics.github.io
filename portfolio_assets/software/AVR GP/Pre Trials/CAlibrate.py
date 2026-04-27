import cv2
import numpy as np
import glob
import json

# ── SETTINGS ─────────────────────────
BOARD_W      = 9       # inner corners wide
BOARD_H      = 6       # inner corners tall
SQUARE_SIZE  = 0.025   # metres — measure yours!
IMAGE_GLOB   = "calib_*.png"
OUTPUT_JSON  = "camera_config.json"
# ─────────────────────────────────────

criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

objp = np.zeros((BOARD_W * BOARD_H, 3), np.float32)
objp[:, :2] = np.mgrid[0:BOARD_W, 0:BOARD_H].T.reshape(-1, 2) * SQUARE_SIZE

obj_points = []   # 3-D points in real world
img_points = []   # 2-D points in image plane

images = glob.glob(IMAGE_GLOB)
print(f"Found {len(images)} images")

for fname in images:
    img  = cv2.imread(fname)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    ok, corners = cv2.findChessboardCorners(gray, (BOARD_W, BOARD_H), None)

    if ok:
        obj_points.append(objp)
        corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
        img_points.append(corners2)

        cv2.drawChessboardCorners(img, (BOARD_W, BOARD_H), corners2, ok)
        cv2.imshow("Corners", img)
        cv2.waitKey(300)
    else:
        print(f"  ⚠ No corners found in {fname}")

cv2.destroyAllWindows()

if len(obj_points) < 10:
    print(f"❌ Only {len(obj_points)} usable frames — need at least 10. Capture more.")
else:
    h, w = cv2.imread(images[0]).shape[:2]
    ret, K, dist, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, (w, h), None, None
    )

    fx = K[0, 0]
    fy = K[1, 1]
    cx = K[0, 2]
    cy = K[1, 2]

    print(f"\n✅ Calibration complete — reprojection error: {ret:.4f} px")
    print(f"   fx={fx:.2f}  fy={fy:.2f}  cx={cx:.2f}  cy={cy:.2f}")

    cfg = {
        "index":       1,
        "width":       w,
        "height":      h,
        "fx":          round(fx, 4),
        "fy":          round(fy, 4),
        "cx":          round(cx, 4),
        "cy":          round(cy, 4),
        "backend":     cv2.CAP_MSMF,
        "auto_detect": True
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(cfg, f, indent=2)

    print(f"   Saved to {OUTPUT_JSON}")
    print(f"   Distortion coefficients: {dist.ravel().round(6)}")
