class Frame:

    def __init__(self, frame):
        self.x = frame[0]
        self.y = frame[1]
        self.z = frame[2]
        self.a = frame[3]
        self.b = frame[4]
        self.c = frame[5]

    def get_x(self):
        return self.x

    def set_x(self, x):
        self.x = x

    def get_y(self):
        return self.y

    def set_y(self, y):
        self.y = y

    def get_z(self):
        return self.z

    def set_z(self, z):
        self.z = z

    def get_a(self):
        return self.a

    def set_a(self, a):
        self.a = a

    def get_b(self):
        return self.b

    def set_b(self, b):
        self.b = b

    def get_c(self):
        return self.c

    def set_c(self, c):
        self.c = c

    def asList(self):
        return [self.x, self.y, self.z, self.a, self.b, self.c]

    def __str__(self):
        return f"{self.x},{self.y},{self.z},{self.a},{self.b},{self.c}"
