import mesa
import mesa_geo as mg
from agents import PersonAgent
from model import GeoSir


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
    "init_infected": mesa.visualization.Slider(
        "Fraction initial infection", 0.2, 0.00, 1.0, 0.05
    ),
    "exposure_distance": mesa.visualization.Slider(
        "Exposure distance", 500, 100, 1000, 100
    ),
}

def agent_draw(agent):
    """
    Portrayal Method for canvas
    """
    portrayal = {}
    if isinstance(agent, PersonAgent):
        portrayal["radius"] = "2"
    if agent.atype in ["hotspot", "infected"]:
        portrayal["color"] = "Red"
    elif agent.atype in ["safe", "susceptible"]:
        portrayal["color"] = "Green"
    elif agent.atype in ["recovered"]:
        portrayal["color"] = "Blue"
    elif agent.atype in ["dead"]:
        portrayal["color"] = "Black"
    return portrayal


map_element = mg.visualization.MapModule(agent_draw)
agents_chart = mesa.visualization.ChartModule(
    [
        {"Label": "infected", "Color": "Red"},
        {"Label": "susceptible", "Color": "Green"},
        {"Label": "recovered", "Color": "Blue"},
        {"Label": "dead", "Color": "Black"},
    ]
)

server = mesa.visualization.ModularServer(
    GeoSir,
    [map_element, Text(), agents_chart],
    "agent-based model",
    model_params,
)
