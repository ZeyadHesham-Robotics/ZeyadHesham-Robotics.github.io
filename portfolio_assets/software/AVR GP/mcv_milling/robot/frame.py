class Frame:
    def __init__(self, frame):
        self.x = frame[0]
        self.y = frame[1]
        self.z = frame[2]
        self.a = frame[3]
        self.b = frame[4]
        self.c = frame[5]

    def asList(self):
        return [self.x, self.y, self.z, self.a, self.b, self.c]

    def __str__(self):
        return f"{self.x},{self.y},{self.z},{self.a},{self.b},{self.c}"
