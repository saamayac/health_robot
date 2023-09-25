import mesa
import mesa_geo as mg

step_size=1 # hours
############## define agent classes
class SpaceAgent(mg.GeoAgent):
    def __init__(self, unique_id, model, geometry, crs, last_id):
        # file loads agent type (atype) and number (number) attributes
        super().__init__(unique_id+last_id, model, geometry, crs)
        self.color_hotspot()
        
    def color_hotspot(self):
        # Decide if there are patients here
        agents = self.model.space.get_intersecting_agents(self)
        patients_here = self.model.filter_agents(agents, lambda x: x.atype=='patient' and x.state=='active')

        if len(patients_here) >= 1:
            self.state = 'ocupied'
        else:
            self.state = 'empty'

    def step(self):
        """Advance agent one step."""
        self.color_hotspot()
        self.model.counts[self.state] += 1  # Count agent state

    def __repr__(self):
        return "Hospital floor " + str(self.unique_id)

from shapely.geometry import Point
class PersonAgent(mg.GeoAgent):
    """Person Agent."""
    def __init__( self, unique_id, model, geometry, crs,
        agent_type, mobility_range=4):

        super().__init__(unique_id, model, geometry, crs)
        
        # Agent type, state, schedule
        self.atype = agent_type
        self.model.counts[agent_type] += 1

        self.state = 'active'
        self.model.counts[self.state] += 1

        if agent_type == 'patient':
            self.stop_working_at = model.steps + self.random.triangular(3*step_size, 6*step_size) # 3-6 hour stay
        else:
            self.stop_working_at = model.steps + 12*step_size # 12 hour shift
        self.mobility_range = mobility_range


    def move_point(self, dx, dy):
        """
        Move a point by creating a new one
        :param di:  Distance to move in i-axis
        """
        new_point = Point(self.geometry.x + dx, self.geometry.y + dy)
        
        # Check if new point is in hospital
        agents = self.model.space.get_intersecting_agents(self)
        in_hospital = self.model.filter_agents(agents, lambda x: x.atype=='floor')

        return new_point if len(in_hospital) > 0 else self.geometry

    def step(self):
        """Advance one step."""
        if self.model.steps > self.stop_working_at :  
            self.state = 'inactive'

        # If not dead, move
        if self.state != 'inactive':
            move_x = self.random.randint(-self.mobility_range, self.mobility_range)
            move_y = self.random.randint(-self.mobility_range, self.mobility_range)
            self.geometry = self.move_point(move_x, move_y)  # Reassign geometry

        # count agents
        self.model.counts[self.state] += 1  
        self.model.counts[self.atype] += 1  

    def __repr__(self):
        return "Person " + str(self.unique_id)
    
############## define model

class GeoModel(mesa.Model): 

    def __init__(self):

        # model parameters
        self.schedule = mesa.time.BaseScheduler(self)
        self.space = mg.GeoSpace(warn_crs_conversion=False)
        self.steps = 0
        self.counts = None; self.reset_counts()
        self.running = True
        self.datacollector = mesa.DataCollector(
            {
                "patient": get_count_patient,
                "medical provider": get_count_medical,
                "inactive": get_count_dead,
                "active": get_count_working,
                "ocupied": get_count_ocupied,
                "empty": get_count_empty
            }
        )
 
        # Generate SpaceAgent population (add to schedule later)
        self.space_agents=[]
        space_file_name=['rooms', 'beds', 'carts','floor']
        last_id=0
        for file in space_file_name:
            file='floorplans/unisabana_hospital_'+file+'.geojson'
            ac = mg.AgentCreator(agent_class=SpaceAgent, model=self, 
                                 agent_kwargs={'last_id':last_id})
            agents = ac.from_file(file)
            self.space.add_agents(agents)
            last_id+=len(agents); self.space_agents+=agents
            
        
        # Generate PersonAgent population
        self.last_person_id=0
        self.add_population(('patient', 5), lambda x: x.atype=='bed')
        self.add_population(('medical provider', 10), lambda x: x.atype=='room')
        self.next_arrival = self.exp_arrival(1/(20*step_size)) # 20 minutes

        # Add the neighbourhood agents to schedule AFTER person agents,
        # to allow them to update their color by using BaseScheduler
        for agent in self.space_agents:
            self.schedule.add(agent)

        self.datacollector.collect(self)

    def filter_agents(self, agent_list, filter_condition):
        return [agent.unique_id for agent in agent_list if filter_condition(agent)]
    
    def exp_arrival(self, rate):
        """Exponential arrival time."""
        return self.steps + self.random.expovariate(1/rate)

    def add_population(self, person_setup, space_agents_filter):
        person_type, person_amount = person_setup
        
        ac_population = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, 
                                        agent_kwargs={'agent_type': person_type})
        
        space_agents_ids=self.filter_agents(self.space_agents, space_agents_filter)
        try:
            sample_spaces_ids = self.random.sample(space_agents_ids, person_amount)
        except ValueError: 
            print("Not enough space to add %i %ss"%(person_amount,person_type))
            sample_spaces_ids = space_agents_ids

        for ix, person_id in zip(range(self.last_person_id,
                               self.last_person_id+person_amount), sample_spaces_ids):
            # posible starting points
            center_x, center_y = self.space_agents[ix].geometry.centroid.coords.xy
            this_bounds = self.space_agents[ix].geometry.bounds

            # Heuristic for agent spread in region
            spread_x = int(this_bounds[2] - this_bounds[0])
            spread_y = int(this_bounds[3] - this_bounds[1])
            this_x = center_x[0] #+ self.random.randint(0, spread_x) - spread_x / 2
            this_y = center_y[0] #+ self.random.randint(0, spread_y) - spread_y / 2

            # create and place Person
            this_person = ac_population.create_agent(Point(this_x, this_y), "P" + str(person_id))
            self.space.add_agents(this_person)
            self.schedule.add(this_person)

        self.last_person_id += person_amount + 1 

    def reset_counts(self):
      self.counts = {
          "patient": 0, "medical provider": 0,
          "active": 0, "inactive": 0,
          "ocupied": 0, "empty": 0 } 

    def step(self):
        """Run one step of the model."""
        self.steps += 1
        self.reset_counts()
        self.schedule.step()

        # Add new patients
        if self.steps > self.next_arrival:
            # Add new patient on empty beds
            empty_beds_filter = lambda x: x.atype=='bed' and x.state=='empty'
            self.add_population(('patient', 1), empty_beds_filter) # add 1 patient
            # Schedule next arrival
            rate=1/(3*step_size) # 3 hours
            self.next_arrival = self.steps + self.exp_arrival(1/rate)

        # Recalculate spatial tree, because agents are moving
        self.space._recreate_rtree()
        self.datacollector.collect(self)

        # Run until no one is in hospital
        if self.counts['active'] == 0:
            self.running = False


# Functions needed for datacollector
def get_count_patient(model): return model.counts["patient"]
def get_count_medical(model): return model.counts["medical provider"]
def get_count_ocupied(model): return model.counts["ocupied"]
def get_count_empty(model): return model.counts["empty"]
def get_count_dead(model): return model.counts["inactive"]
def get_count_working(model): return model.counts["active"]

