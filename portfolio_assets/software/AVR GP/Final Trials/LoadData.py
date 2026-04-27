class LoadData:
    def __init__(self,mass,cm,inertia):
        self._mass = mass
        self._cm = cm
        self._inertia= inertia

    # getter method
    def get_mass(self):
        return self._mass
      
    # setter method
    def set_mass(self, mass):
        self._mass = mass
    
    # getter method
    def get_cm(self):
            return self._cm
        
    # setter method
    def set_cm(self, cm):
        self._cm = cm

    # getter method
    def get_inertia(self):
        return self._inertia
      
    # setter method
    def set_inertia(self, inertia):
        self._inertia = inertia

    def __str__(self):
        return "Mass: "+str(self._mass) +", CM: "+','.join(self._cm)+",Inertia: "+','.join(self._inertia)