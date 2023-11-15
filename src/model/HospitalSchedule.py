from mesa.time import BaseScheduler
from mesa.model import Model
import random 

class HospitalScheduler(BaseScheduler):
    def __init__(self, model: Model) -> None: 
        super().__init__(model)
        self.patient_arrivals=[]

    def step(self) -> None:
        """Execute the step of all the agents, one at a time."""
        # To be able to remove and/or add agents during stepping
        # it's necessary for the keys view to be a list.
        super().step()

        # Add new patients
        n_new_patients=self.patient_arrivals.count(self.steps)
        if n_new_patients > 0:
            self.model.add_PersonAgents(self.model.ac_patients, n_new_patients, self.model.space.get_empty_beds(n_new_patients))

