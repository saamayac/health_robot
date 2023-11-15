import mesa_geo as mg

class SpaceAgent(mg.GeoAgent):
    def __init__(self, unique_id, model, geometry, crs):
        # file loads agent type (atype) and number (number) attributes
        super().__init__(unique_id, model, geometry, crs)
        self.state = 'empty'
        self.count_agents()
        
    def step(self):
        """Advance agent one step."""
        self.get_bed_ocupation()
        self.count_agents()

    def get_bed_ocupation (self):
        """Color beds according to number of active patients."""
        if self.atype=='bed':
            # Find active patients in this space
            patient_here=self.model.space.get_relation_to_AgentCentroid(self, 'intersects', 'patient') 
            self.state = 'ocupied' if patient_here else 'empty'           

    def __repr__(self):
        return "SpaceAgent_"+str(self.unique_id)
    
    def set_ocupied(self):
        """Set bed as ocupied."""
        self.state = 'ocupied'
        self.model.counts['ocupied'] += 1
        self.model.counts['empty'] -= 1
    
    def count_agents(self):
        """Count agents in model."""
        self.model.counts[self.state] += 1

