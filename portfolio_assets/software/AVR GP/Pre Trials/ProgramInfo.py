class ProgramInfo:
   
    # getter method
    def get_programName(self):
        return self._programName
      
    # setter method
    def set_programName(self, programName):
        self._programName = programName
    
    # getter method
    def get_programState(self):
        return self._programState
      
    # setter method
    def set_programState(self, programState):
        self._programState = programState

    
    def __str__(self):
        return "Program name:  "+self._programName +", program state:  "+self._programState