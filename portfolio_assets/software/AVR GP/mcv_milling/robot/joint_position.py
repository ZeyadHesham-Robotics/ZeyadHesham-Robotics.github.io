class JointPosition:
    def __init__(self, robotAxes, externalAxes):
        self._robotAxes = robotAxes
        self._externalAxes = externalAxes

    def get_robotAxes(self):
        return self._robotAxes

    def get_externalAxes(self):
        return self._externalAxes
