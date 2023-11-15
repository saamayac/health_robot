from collections import defaultdict
from typing import DefaultDict, Dict, Optional, Set, Tuple

import mesa
import mesa_geo as mg
from shapely.geometry import Point
import random
from itertools import cycle

from agents.SpaceAgent import SpaceAgent
from agents.PersonAgent import PersonAgent


class Hospital(mg.GeoSpace): # inherits from mesa_geo.GeoSpace
    # Space agents
    rooms: Set[SpaceAgent]
    beds: Dict[SpaceAgent, Tuple[SpaceAgent]]
    nurse_station: SpaceAgent
    medication_station: SpaceAgent
    floor: SpaceAgent

    def __init__(self) -> None:
        super().__init__(warn_crs_conversion=False)
        # initialize sets of Agents
        self.rooms = set()
        self.beds = {}
        self.available_beds = 0

    def compare_path_bounds(self, path_bounds, start, end) -> bool:
        path_a, path_b = path_bounds
        return path_a.within(start.buffer(0.2)) and path_b.within(end.buffer(0.2))

    def compare_placement(self, agent, other_agent) -> bool:
        """Return True if the agent is within the other_agent."""
        return agent.geometry.centroid.within(other_agent.geometry.centroid.buffer(0.2)) # within 0.2 meter of each other

    def add_spaces(self, agents) -> None:
        super().add_agents(agents)
        beds_aux = []
        for agent in agents:
            assert isinstance(agent,SpaceAgent)
            if agent.atype == 'room':
                self.rooms.add(agent)
            if agent.atype == 'bed':
                bed_room=self.get_relation_to_AgentCentroid(agent, 'within', 'room')
                beds_aux.append((bed_room,agent))
                self.available_beds += 1
            elif agent.atype == 'nurse_station':
                self.nurse_station = agent
            elif agent.atype == 'medication_station':
                self.medication_station = agent
            elif agent.atype == 'floor':
                self.floor = agent
        self.beds = {room: [] for room in self.rooms}
        for room, bed in beds_aux: self.beds[room].append(bed)

    def get_empty_beds(self, amount) -> Set[SpaceAgent]:
        """Return an empty bed on the rooms with the least number of ocupied beds."""
        empty_beds=[]
        for _ in range(amount):
            rooms_by_empty_beds = sorted(self.beds.items(), key=lambda item: len(list(filter(lambda x: x.state=='ocupied', item[1]))))
            for room, beds in rooms_by_empty_beds:
                this_empty_bed=next((bed for bed in beds if bed.state=='empty'), None)
                if this_empty_bed is not None:
                    empty_beds.append(this_empty_bed)
                    this_empty_bed.set_ocupied()
                    break
        if len(empty_beds)==amount: return empty_beds
        else: raise Exception("Not enough empty beds")
          
        
    def filter_agents(self, filter):
        return [agent for agent in self.agents if filter(agent)]
    
    def get_relation_to_AgentCentroid(self, agent, relation, agent_type):
        """Return a list of related agents.

        Parameters:
            agent: the agent for which to compute the relation
            relation: must be one of 'intersects', 'within', 'contains', 'touches'
            agent_type: the type of agent to look for
        """

        possible_agents = self._agent_layer._get_rtree_intersections(agent.geometry.centroid)
        for other_agent in possible_agents:
            if (
                getattr(agent.geometry.centroid, relation)(other_agent.geometry)
                and other_agent.unique_id != agent.unique_id
                and other_agent.atype == agent_type
            ):
                #yield other_agent # this is a generator of all matches
                return other_agent # return first match
        # if no match was found
        return None
