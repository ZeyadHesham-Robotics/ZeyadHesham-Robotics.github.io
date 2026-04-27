class CartesianPosition:

    def __init__(self, frame=None):
        if frame is None:
            self.frame = [0, 0, 0, 0, 0, 0]
        else:
            self.frame = frame

    def set_frame(self, frame):
        self.frame = frame

    def asArray(self):
        return self.frame