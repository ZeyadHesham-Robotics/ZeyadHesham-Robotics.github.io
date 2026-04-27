
class JointPosition:

    def __init__(self,robotAxes,externalAxes):
        self._robotAxes = robotAxes
        self._externalAxes = externalAxes

    # getter method
    def get_robotAxes(self):
        return self._robotAxes
      
    # setter method
    def set_robotAxes(self, robotAxes):
        self._robotAxes = robotAxes
    
    # getter method
    def get_externalAxes(self):
        return self._externalAxes
      
    # setter method
    def set_externalAxes(self, externalAxes):
        self._externalAxes = externalAxes
  