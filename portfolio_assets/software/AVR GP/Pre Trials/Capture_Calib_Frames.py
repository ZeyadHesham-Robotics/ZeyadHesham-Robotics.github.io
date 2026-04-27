import cv2

CAMERA_INDEX = 1
cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_MSMF)

count = 0
while True:
    ret, frame = cap.read()
    cv2.imshow("Calibration capture — press S to save, Q to quit", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("s"):
        cv2.imwrite(f"calib_{count:03d}.png", frame)
        print(f"Saved calib_{count:03d}.png")
        count += 1
    elif key == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()