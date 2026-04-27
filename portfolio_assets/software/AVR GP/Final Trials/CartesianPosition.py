from Frame import Frame


class CartesianPosition:

    def __init__(self, frame=None, status=None, turn=None, external_axes=None):
        if frame is None:
            self.frame = Frame([0, 0, 0, 0, 0, 0])
        elif isinstance(frame, Frame):
            self.frame = frame
        else:
            self.frame = Frame(frame)
        self.status = status
        self.turn = turn
        self.external_axes = external_axes if external_axes is not None else []

    def set_frame(self, frame):
        if isinstance(frame, Frame):
            self.frame = frame
        else:
            self.frame = Frame(frame)

    def asArray(self):
        result = self.frame.asList()
        if self.status is not None:
            result.append(self.status)
        if self.turn is not None:
            result.append(self.turn)
        result.extend(self.external_axes)
        return result

    def __str__(self):
        ext = ','.join(str(e) for e in self.external_axes)
        return (f"Frame: {self.frame}, Status: {self.status}, "
                f"Turn: {self.turn}, External: {ext}")
