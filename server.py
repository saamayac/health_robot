import mesa
import mesa_geo as mg
from geo_model import PersonAgent, GeoModel

############## define server

class Text(mesa.visualization.TextElement):
    """
    Display a text
    """
    def __init__(self):
        pass

    def render(self, model):
        return "Steps: " + str(model.steps)


model_params = {
    "pop_size": mesa.visualization.Slider("Population size", 30, 10, 100, 10),
}

def agent_draw(agent):
    """
    Portrayal Method for canvas
    """
    portrayal = {}
    if isinstance(agent, PersonAgent): portrayal["radius"] = "2"

    if agent.atype in ["ocupied"]: portrayal["color"] = "Red"
    elif agent.atype in ["empty"]: portrayal["color"] = "Green"

    elif agent.atype in ["patient"]: portrayal["color"] = "Grey"
    elif agent.atype in ["medical provider"]: portrayal["color"] = "Black"
    elif agent.atype in ["dead"]: portrayal["color"] = "Yellow"
    return portrayal

map_element = mg.visualization.MapModule(agent_draw,view={'lng': -74.030387, 'lat': 4.856246},
                                         zoom=30,scale_options={'metric':True,'setMaxZoom':300}) 

agents_chart = mesa.visualization.ChartModule(
    [
        {"Label": "medical provider", "Color": "Black"},
        {"Label": "patient", "Color": "Grey"},
        {"Label": "dead", "Color": "Yellow"},
    ]
)   
  
server = mesa.visualization.ModularServer(
    GeoModel,
    [map_element, Text(), agents_chart],
    "agent-based model",
    model_params,
)