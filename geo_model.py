import mesa
import mesa_geo as mg

############## define agent classes
class Hospital(mg.GeoAgent):
    def __init__(self, unique_id, model, geometry, crs, last_id):
        super().__init__(unique_id+last_id, model, geometry, crs)
        self.color_hotspot()
        self.atype='floor'

    def color_hotspot(self):
        # Decide if there are patients here
        agents = self.model.space.get_intersecting_agents(self)
        patients_here = [patient for patient in agents if patient.atype == "patient"]

        if len(patients_here) >= 1:
            self.state = "ocupied"
        else:
            self.state = "empty"

    def step(self):
        """Advance agent one step."""
        self.color_hotspot()
        self.model.counts[self.state] += 1  # Count agent type
        # self.model.counts[self.atype] += 1  # Count agent type

    def __repr__(self):
        return "Hospital floor " + str(self.unique_id)

from shapely.geometry import Point
class PersonAgent(mg.GeoAgent):
    """Person Agent."""
    def __init__( self, unique_id, model, geometry, crs,
        agent_type="patient",
        mobility_range=4, # movement per step
        p_worker=0.5,
    ):
        super().__init__(unique_id, model, geometry, crs)
        # Agent parameters
        self.state = 'working'
        self.model.counts["working"] += 1
        self.mobility_range = mobility_range
 
        # Random choose if healthcare worker
        self.atype = agent_type
        self.model.counts[agent_type] += 1
        if self.random.random() < p_worker:
            self.atype = "medical provider"
            self.model.counts["patient"] -= 1  # Adjust initial counts
            self.model.counts["medical provider"] += 1

    def move_point(self, dx, dy):
        """
        Move a point by creating a new one
        :param dx:  Distance to move in x-axis
        :param dy:  Distance to move in y-axis
        """
        return Point(self.geometry.x + dx, self.geometry.y + dy)

    def step(self):
        """Advance one step."""
        if self.random.random() < 0.1: self.state = "dead"

        # If not dead, move
        if self.state != "dead":
            move_x = self.random.randint(-self.mobility_range, self.mobility_range)
            move_y = self.random.randint(-self.mobility_range, self.mobility_range)
            self.geometry = self.move_point(move_x, move_y)  # Reassign geometry

        self.model.counts[self.state] += 1  # Count agent type
        self.model.counts[self.atype] += 1  # Count agent type

    def __repr__(self):
        return "Person " + str(self.unique_id)
    
############## define model

class GeoModel(mesa.Model): 

    def __init__(self, pop_size=3):
        self.schedule = mesa.time.BaseScheduler(self)
        self.space = mg.GeoSpace(warn_crs_conversion=False)
        self.steps = 0
        self.counts = None
        self.reset_counts()

        # model parameters
        self.pop_size = pop_size
        self.counts["patient"] = pop_size
        self.counts["working"] = pop_size

        self.running = True
        self.datacollector = mesa.DataCollector(
            {
                "patient": get_count_patient,
                "medical provider": get_count_medical,
                "dead": get_count_dead,
                "working": get_count_working,
                "ocupied": get_count_ocupied,
                "empty": get_count_empty
            }
        )
 
        # Set up the room patches for every polygon in file
        # (add to schedule later)
        ac = mg.AgentCreator(agent_class=Hospital, model=self, agent_kwargs={'last_id':0})
        room_file='floorplans/unisabana_hospital_rooms.geojson'
        room_agents = ac.from_file(room_file)
        self.space.add_agents(room_agents)

        ac = mg.AgentCreator(agent_class=Hospital, model=self, agent_kwargs={'last_id':len(room_agents)})
        room_file='floorplans/unisabana_hospital_beds.geojson'
        floor_agents = ac.from_file(room_file)
        self.space.add_agents(floor_agents)

        space_agents=room_agents+floor_agents

        # Generate PersonAgent population
        ac_population = mg.AgentCreator( PersonAgent, model=self, 
                                        crs=self.space.crs)

        # Generate random location, add agent to grid and scheduler
        for i in range(pop_size):
             # Region where agent starts
            this_neighbourhood = self.random.randint(0, len(room_agents) - 1)

            center_x, center_y = room_agents[this_neighbourhood].geometry.centroid.coords.xy
            this_bounds = room_agents[this_neighbourhood].geometry.bounds

            # Heuristic for agent spread in region
            spread_x = int(this_bounds[2] - this_bounds[0])
            spread_y = int(this_bounds[3] - this_bounds[1])
            this_x = center_x[0] + self.random.randint(0, spread_x) - spread_x / 2
            this_y = center_y[0] + self.random.randint(0, spread_y) - spread_y / 2
 
            # create and place Person
            this_person = ac_population.create_agent(Point(this_x, this_y), "P" + str(i))
            self.space.add_agents(this_person)
            self.schedule.add(this_person)

        # Add the neighbourhood agents to schedule AFTER person agents,
        # to allow them to update their color by using BaseScheduler
        for agent in space_agents:
            self.schedule.add(agent)

        self.datacollector.collect(self)

    def reset_counts(self):
      self.counts = {
          "patient": 0,
          "medical provider": 0,
          "working": 0,
          "dead": 0,
          "ocupied": 0,
          "empty": 0 } 

    def step(self):
        """Run one step of the model."""
        self.steps += 1
        self.reset_counts()
        self.schedule.step()
        # Recalculate spatial tree, because agents are moving
        self.space._recreate_rtree()

        self.datacollector.collect(self)

        # Run until no one is in hospital
        if self.counts["working"] == 0:
            self.running = False


# Functions needed for datacollector
def get_count_patient(model): return model.counts["patient"]
def get_count_medical(model): return model.counts["medical provider"]
def get_count_ocupied(model): return model.counts["ocupied"]
def get_count_empty(model): return model.counts["empty"]
def get_count_dead(model): return model.counts["dead"]
def get_count_working(model): return model.counts["working"]

