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


# model_params = {"pop_size": mesa.visualization.Slider("Population size", 30, 10, 100, 10)}

def agent_draw(agent):
    """
    Portrayal Method for canvas
    """
    portrayal = {}
    if isinstance(agent, PersonAgent): portrayal["radius"] = "1"

    if agent.state in ["ocupied"]: portrayal["color"] = "Red"
    elif agent.state in ["empty"]: portrayal["color"] = "Green"

    elif agent.state in ["inactive"]: portrayal["color"] = "Yellow"
    elif agent.atype in ["patient"]: portrayal["color"] = "Blue"
    elif agent.atype in ["medical provider"]: portrayal["color"] = "Black"
    
    return portrayal

map_element = mg.visualization.MapModule(agent_draw,view={'lng': -74.030387, 'lat': 4.856246},
                                         zoom=30,scale_options={'metric':True,'setMaxZoom':300}) 

agents_chart = mesa.visualization.ChartModule(
    [
        {"Label": "medical provider", "Color": "Black"},
        {"Label": "patient", "Color": "Grey"},
        {"Label": "inactive", "Color": "Yellow"},
    ]
)   
  
server = mesa.visualization.ModularServer(
    GeoModel,
    [map_element, Text(), agents_chart], 
    "agent-based model",
    #model_params,
)