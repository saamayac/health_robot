import mesa
import mesa_geo as mg

from agents.PersonAgent import PersonAgent
from agents.SpaceAgent import SpaceAgent
from agents.HospitalAgent import Hospital
from model.Schedulers import HospitalScheduler

from os.path import join
import geopandas as gpd 
import pandas as pd
import random

class GeoModel(mesa.Model): 

    def __init__(self, n_doctors=2, n_nurses=3, ocupation=10):
        self.running = True
        self.schedule = HospitalScheduler(self)
        self.current_id=0

        # Scheduled actions time
        self.resample_variables()
        self.action_state = {'remove': 'leaving',
                             
                             # shift actions
                             'do-informative-meeting': 'in-meeting',
                             'do-inventory': 'taking-inventory',
                             'do-document': 'documenting',

                             # patient-related actions
                             'do-admit': 'admitting',
                             'do-evaluate': 'evaluating', 
                             'do-medicate': 'medicating',

                             # patient actions
                             'request-admission': 'waiting-admission', # starts 'in-admission' and ends in 'admitted'
                             'request-evaluation': 'waiting-evaluation', # starts 'in-evaluation' and ends in 'evaluated'
                             'request-medication': 'waiting-medication', # starts 'in-medication' and ends in 'medicated'
                             }

        # counts for performance metrics
        self.collected_fields = ["doctor", "nurse", "patient", "idle", "walking","removed",
                                 'in-admission','admitted',
                                 'in-evaluation','evaluated',
                                 'in-medication','medicated'] + list(self.action_state.values())
        self.reset_counts()
        self.metric_fields = ['walking','documenting','admitting','evaluating','medicating','taking-inventory','in-meeting']
        self.reset_metrics()

        # create hospital space
        self.space = Hospital()
        self.doctors=[]; self.nurses=[]

        # SpaceAgents: read from files and add to model
        file_path=join ('data','floorplans','unisabana_hospital_%s.geojson')
        file_names=['floor','polygons']
        df_space = pd.concat((gpd.read_file(file_path%file) for file in file_names),ignore_index=True)
        space_agents = mg.AgentCreator(agent_class=SpaceAgent, model=self).from_GeoDataFrame(df_space)  
        self.space.add_SpaceAgents(space_agents)
 
        # PersonAgent Constructors 
        n_patients=int(ocupation*self.space.floor.patient_availability/100)
        self.init_poputation(n_doctors, n_nurses, n_patients)

        # Add the SpaceAgents to schedule AFTER person agents, to allow them to update their ocupation by using BaseScheduler   
        for agent in space_agents: self.schedule.add(agent)

        # collect initialization data
        self.initialize_data_collector()

    def resample_variables(self):
        # lifetime related
        self.patient_stay_length = random.triangular(2*60, 3*60)
        self.time_between_patients=random.triangular(5, 10)
        self.shift_length = 12*60

        # shift related
        self.walking_speed=15 # steps per time tick
        self.shift_transfer_meeting_time = random.triangular(15, 20)
        self.inventory_time = random.triangular(15, 20)

        # patient related
        self.medicine_round_frequency = random.triangular(60, 120)
        self.admission_time = random.triangular(5, 10)
        self.evaluation_time = random.triangular(5, 10)
        self.evaluation_frequency = random.triangular(60, 120)
        

    def init_poputation(self, n_doctors, n_nurses, n_patients):
        """Add population to model."""
        # AgentCreators
        self.ac_doctors = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'doctor'})
        self.ac_nurses = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'nurse'})
        self.ac_patients = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'patient'})
        # add agents
        self.add_PersonAgents(self.ac_doctors, n_doctors, self.space.nurse_station)
        self.add_PersonAgents(self.ac_nurses, n_nurses, self.space.nurse_station)
        for _ in range(n_patients): # add patients at different times
            self.schedule.patient_arrivals.append(self.schedule.steps + int(self.time_between_patients))
            self.resample_variables()

    def add_PersonAgents(self, agentCreator, amount, this_spaces, do_shift_takeover=False): 
        """Add population to model."""
        if isinstance(this_spaces,SpaceAgent): this_spaces=[this_spaces]*amount 
        for this_space in this_spaces:
            # create person on this_space centroid
            this_person = agentCreator.create_agent(this_space.geometry.centroid, "P%i"%super().next_id())
            self.schedule.add(this_person)
            self.space.add_agents(this_person)
            # return person if shift takeover is needed
            if do_shift_takeover: return this_person
    
    def initialize_data_collector(self) -> None:
        """Initialize data collector."""
        model_reporters={key : [lambda key: self.counts[key], [key]] for key in self.counts}
        metric_reporters={state+'_%' : [lambda state: self.metrics[state], [state]] for state in self.metrics}
        agent_reporters={'atype':'atype', 'position':'geometry', 'state':'state'}
        self.datacollector = mesa.DataCollector({**model_reporters,**metric_reporters}, agent_reporters, tables=None)
        self.datacollector.collect(self)

    def reset_counts(self):
        self.counts = dict.fromkeys(self.collected_fields,0)

    def reset_metrics(self):
        self.metrics = dict.fromkeys(self.metric_fields, 0)
        self.metrics.update({'not-'+key : 1 for key in self.metric_fields})

    def update_metrics(self, people_list):
        ''''Update metrics with the current state of the agents in people_list'''
        for key in self.metric_fields:
            true_key=0; prev_running_time=0; active_agents=0
            for agent in people_list:
                if agent.life_span>0:
                    true_key+=agent.state==key
                    prev_running_time+=agent.life_span-1
                    active_agents+=1
            if active_agents>0:
                self.metrics[key]=(self.metrics[key]*prev_running_time + true_key)/(prev_running_time+len(people_list))
                self.metrics['not-'+key]=1-self.metrics[key]

    def step(self):
        """Run one step of the model."""
        self.reset_counts()
        self.schedule.step()
        self.update_metrics(self.nurses)
        self.space._recreate_rtree() # Recalculate spatial tree, because agents are moving
        self.datacollector.collect(self) # collect data

        # Run until no one is working in the hospital
        if self.schedule.steps>self.shift_length:
            self.running = False
            # collect dataframes into csv files
            self.datacollector.get_agent_vars_dataframe().to_csv(join('data','agents.csv'))
            self.datacollector.get_model_vars_dataframe().to_csv(join('data','model.csv'))
            print("running for ", self.schedule.steps, " steps")