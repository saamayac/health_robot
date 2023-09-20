import mesa
import mesa_geo as mg

geojson_states = "data/TorontoNeighbourhoods.geojson"

class State(mg.GeoAgent):
    def __init__(self, unique_id, model, geometry, crs):
        super().__init__(unique_id, model, geometry, crs)


class GeoModel(mesa.Model):
    def __init__(self):
        self.space = mg.GeoSpace()

        ac = mg.AgentCreator(agent_class=State, model=self)
        agents = ac.from_GeoJSON(GeoJSON=geojson_states, unique_id="NAME")
        self.space.add_agents(agents)



m = GeoModel()

agent = m.space.agents[0]
print(agent.unique_id)
print(agent.geometry)
