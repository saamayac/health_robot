from mesa.datacollection import DataCollector

class HospitalData(DataCollector):
    """Class to collect data from the model."""
    def __init__(self, model_reporters=None, agent_reporters=None, tables=None):
        super().__init__(model_reporters, agent_reporters, tables)

    def collect(self, model):
        """Collect all the data for the given model object."""
        if self.model_reporters:
            for var, reporter in self.model_reporters.items():
                self.model_vars[var].append(reporter[var])

        if self.agent_reporters:
            agent_records = self._record_agents(model)
            self._agent_records[model.schedule.steps] = list(agent_records)