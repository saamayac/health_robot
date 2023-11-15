import mesa
import mesa_geo as mg

from agents.PersonAgent import PersonAgent
from agents.SpaceAgent import SpaceAgent
from agents.HospitalAgent import Hospital

from model.HospitalSchedule import HospitalScheduler
from model.d_star_lite import DStarLite

from os.path import join
from shapely.geometry import Point
import geopandas as gpd 
import pandas as pd
import random
import pickle
from functools import partial

class GeoModel(mesa.Model): 

    def __init__(self, n_doctors=2, n_nurses=3, ocupation=10):
        self.running = True
        self.schedule = HospitalScheduler(self)
        self.current_id=0
        self.walking_speed=15 # steps per time tick

        # counts for performance metrics
        self.worker_states=['admiting','documenting','checking-medicine','documenting-risk']
        self.patient_states=['waiting_admission','in-admission'] # risk-evaluation (def freq. visit by gravity), aplicacion-med, egreso
        self.collected_fields = ["doctor","nurse","patient",
                                 "walking", "waiting_instruction","ocupied","empty",
                                ]+self.worker_states+self.patient_states
        self.reset_counts() 
        self.metric_fields=['walking','documenting']
        self.reset_metrics()

        # Scheduled actions time
        self.resample_task_times()
        self.action_state = {'do-admit': 'admiting',
                             'do-document': 'documenting',
                             'do-medicine-check': 'checking-medicine',
                             'do-document-risk': 'documenting', #'documenting-risk', 
                             'in-admission': 'in-admission',
                             }

        # create hospital space
        self.space = Hospital()
        # check: self.space.crs.name for distance object
        self.doctors=[]; self.nurses=[]

        # SpaceAgents: read from files and add to model
        file_path=join ('data','floorplans','unisabana_hospital_%s.geojson')
        file_names=['floor','polygons']
        df_space = pd.concat((gpd.read_file(file_path%file) for file in file_names),ignore_index=True)
        space_agents = mg.AgentCreator(agent_class=SpaceAgent, model=self).from_GeoDataFrame(df_space)  
        self.space.add_spaces(space_agents)
 
        # PersonAgent Constructors 
        n_patients=int(ocupation*self.space.available_beds/100)
        self.init_poputation(n_doctors, n_nurses, n_patients) 

        # Add the SpaceAgents to schedule AFTER person agents, to allow them to update their ocuopation by using BaseScheduler   
        for agent in self.space.filter_agents(lambda a: isinstance(a, SpaceAgent)):  self.schedule.add(agent)

        # prepare path creation object and load previous paths
        self.dstarlite = DStarLite(self.space.floor, zoom_factor=0.09)
        try: 
            with open("data/paths/cache_paths.pkl", "rb") as cache_file:
                self.cache_paths = pickle.load(cache_file)
        except:
            self.cache_paths = {}

        # collect initialization data
        self.initialize_data_collector()
        print('agents initialized')

    def resample_task_times(self):
        self.consult_time = random.triangular(10, 20)
        self.review_time = random.triangular(5, 10)
        self.patient_stay_length = random.triangular(2*60, 3*60)
        self.shift_length = 12*60
        self.check_medicine_cart_time = random.triangular(15, 20) 
        self.admission_time = random.triangular(5, 10)
        self.time_between_patients=random.triangular(5, 10)

    def init_poputation(self, n_doctors, n_nurses, n_patients):
        """Add population to model."""
        # AgentCreators
        self.ac_doctors = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'doctor'})
        self.ac_nurses = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'nurse'})
        self.ac_patients = mg.AgentCreator( PersonAgent, model=self, crs=self.space.crs, agent_kwargs={'agent_type': 'patient'})
        # add agents
        self.add_PersonAgents(self.ac_doctors, n_doctors, self.space.nurse_station)
        self.add_PersonAgents(self.ac_nurses, n_nurses, self.space.nurse_station)
        self.add_PersonAgents(self.ac_patients, n_patients, self.space.get_empty_beds(n_patients))

    def add_PersonAgents(self, agentCreator, amount, this_spaces, do_shift_takeover=False): 
        """Add population to model."""
        if isinstance(this_spaces,SpaceAgent): this_spaces=[this_spaces]*amount 

        for this_space in this_spaces:
            # create person on this_space centroid
            this_person = agentCreator.create_agent(this_space.geometry.centroid, "P%i"%super().next_id())
            self.schedule.add(this_person)
            self.space.add_agents(this_person)

            # add to lists of agents according to type
            if agentCreator.agent_kwargs['agent_type']=='doctor':
                this_person.patients=[]
                self.doctors.append(this_person)
                if do_shift_takeover: return this_person
            elif agentCreator.agent_kwargs['agent_type']=='nurse':
                this_person.patients=[] 
                self.nurses.append(this_person)
                if do_shift_takeover: return this_person
            elif agentCreator.agent_kwargs['agent_type']!='patient': raise NameError('AgentTypeNotDefined')
    
    def initialize_data_collector(self) -> None:
        """Initialize data collector."""
        model_reporters={key : [lambda key: self.counts[key], [key]] for key in self.counts}
        metric_reporters={state+'_%' : [lambda state: self.metrics[state], [state]] for state in self.metrics}
        
        agent_reporters={'atype':'atype', 'position':'geometry', 'state':'state'}
        self.datacollector = mesa.DataCollector({**model_reporters,**metric_reporters}, agent_reporters, tables=None)
        self.datacollector.collect(self)

    def reset_counts(self):
        self.counts = { key : 0 for key in self.collected_fields}

    def reset_metrics(self):
        self.metrics = { key : 0 for key in self.metric_fields}
        self.metrics.update({ 'not-'+key : 1 for key in self.metric_fields})

    def update_metrics(self):
        for key in self.metric_fields:
            true_key=0; prev_running_time=0; working_nurses=0
            for nurse in self.nurses:
                if nurse.life_span>0:
                    true_key+=nurse.state==key
                    prev_running_time+=nurse.life_span-1
                    working_nurses+=1
            if working_nurses>0:
                self.metrics[key]=(self.metrics[key]*prev_running_time + true_key)/(prev_running_time+len(self.nurses))
                self.metrics['not-'+key]=1-self.metrics[key]
    
    def step(self):
        """Run one step of the model."""
        self.reset_counts()
        self.schedule.step()
        self.update_metrics()
        self.space._recreate_rtree() # Recalculate spatial tree, because agents are moving
        self.datacollector.collect(self) # collect data

        # Run until no one is working in the hospital
        if self.schedule.steps>self.shift_length:
            self.running = False
            # collect dataframes into csv files
            self.datacollector.get_agent_vars_dataframe().to_csv(join('data','agents.csv'))
            self.datacollector.get_model_vars_dataframe().to_csv(join('data','model.csv'))
            print("running for ", self.schedule.steps, " steps")