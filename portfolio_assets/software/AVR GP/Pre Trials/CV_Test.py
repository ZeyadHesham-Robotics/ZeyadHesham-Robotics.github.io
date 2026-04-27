import cv2

def list_available_cameras(max_index_to_check=10):
    """
    Checks the first 'max_index_to_check' indices and returns a list of 
    those that successfully open a video capture and read a frame.
    """
    available_cameras = []
    for index in range(max_index_to_check):
        cap = cv2.VideoCapture(index)
        # Check if the VideoCapture object was opened successfully
        if cap.isOpened():
            # Try to read a frame to confirm it's actually working
            ret, frame = cap.read()
            if ret:
                available_cameras.append(index)
                print(f"Camera found at index: {index} (Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))})")
            else:
                print(f"Camera at index {index} is present but not reading frames.")
            cap.release() # Release the camera immediately after checking
        else:
            print(f"No camera found or unable to open index: {index}")
            
    return available_cameras

if __name__ == "__main__":
    working_cameras = list_available_cameras()
    print(f"\nWorking camera indices: {working_cameras}")
