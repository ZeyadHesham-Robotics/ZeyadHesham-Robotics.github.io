class Frame:
    
    def __init__(self,frame):
        self.x = frame[0]
        self.y = frame[1]
        self.z = frame[2]
        self.a = frame[3]
        self.b = frame[4]
        self.c = frame[5]

     
    # getter method
    def get_x(self):
        return self._x
      
    # setter method
    def set_x(self, x):
        self.x = x
         
    # getter method
    def get_y(self):
        return self._y
      
    # setter method
    def set_y(self, y):
        self.y = y

    # getter method
    def get_z(self):
        return self._z
      
    # setter method
    def set_z(self, z):
        self.z = z

    # getter method
    def get_a(self):
        return self._a
      
    # setter method
    def set_a(self, a):
        self._a= a
    
    # getter method
    def get_b(self):
        return self._b
      
    # setter method
    def set_b(self, b):
        self.b = b

    # getter method
    def get_c(self):
        return self._c
      
    # setter method
    def set_c(self, c):
        self._c= c

    def asList(self):
        return [self.x,self.y,self.z,self.a,self.b,self.c]
    
    def __str__(self):
        return self.x +","+self.y+","+self.z+","+self.a+","+self.b+","+self.c

   
   