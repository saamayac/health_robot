import mesa_geo as mg
from shapely.geometry import Point
import random
import pickle

class PersonAgent(mg.GeoAgent):

    def __init__(self, unique_id, model, geometry, crs, agent_type):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs)
        self.atype = agent_type 
        self.set_to_not_busy()
        self.set_cutoff_time()
        self.schedule = [] # {(action, action_params)}
        self.count_agents()
        if self.atype=='patient':
            self.request_admission()
        if self.atype=='nurse':
            self.start_nurse_shift()
        self.interacting_with=None
        self.life_span=0
    
    def step(self):
        """Advance one step"""
        self.do_scheduled_actions()
        if self.interacting_with: self.do_interactions()
        self.model.resample_task_times()
        if (self.model.schedule.steps >= self.cutoff_time) and not self.busy: self.remove()
        else: 
            self.count_agents()
            self.life_span+=1
    
    def __repr__(self):
        return "PersonAgent_"+str(self.unique_id)

    def do_scheduled_actions(self):

        if not self.busy:
            self.prepare_next_action()

        if self.state=='walking':
            # if following a path: move to next point until arrived
            for _ in range(self.model.walking_speed):
                self.geometry = Point(self.path.pop(0))
                if len(self.path)==0: # if arrived, prepare to finish task
                    self.prepare_next_action()
                    break

        elif self.state in self.model.worker_states:
            # if doing a task: wait until task finishes
            if self.model.schedule.steps >= self.busy_until: 
                if self.interacting_with: self.do_interactions(shut_interaction=True)
                self.set_to_not_busy()
                

    def prepare_next_action(self):
        
        if self.next_action is None: 
            try: # check if there is a new action to do
                self.next_action, self.next_action_args = self.schedule.pop(0)
                self.busy = True
            except IndexError: 
                pass
        
        if self.next_action in ['do-admit','do-document','do-medicine-check','do-document-risk']:
            task_receivers, task_time  = self.next_action_args
            
            # check if the agent is already in the required location
            if self.model.space.compare_placement(self, task_receivers[-1]):
                self.state = self.model.action_state[self.next_action]
                self.busy_until = self.model.schedule.steps + task_time
                if isinstance(task_receivers[-1], PersonAgent):
                    self.interacting_with=task_receivers[-1]; task_receivers[-1].interacting_with=self
            
            else: # walk the required locations
                self.link_paths(task_receivers)             
                self.state='walking'

    def do_interactions(self, shut_interaction=False):
        if self.state=='admiting':
            self.interacting_with.state='in-admission'
            self.interacting_with.busy=True

        if shut_interaction:
            self.interacting_with.interacting_with=None
            self.interacting_with.busy=False

    def set_to_not_busy(self):
        self.busy = False
        self.busy_until = None
        self.state='waiting_instruction'
        self.next_action = None
        self.interacting_with = None

    def request_admission(self):
        self.state='waiting_admission'
        self.busy=True
        # assign to doctor & nurse with least patients
        doctor=sorted(self.model.doctors, key=lambda doc: len(doc.patients))[0]
        doctor.patients.append(self)
        nurse=sorted(self.model.nurses, key=lambda nurse: len(nurse.patients))[0]
        nurse.patients.append(self)

        # schedule admission tasks
        nurse.schedule.append(('do-admit', ([self], self.model.admission_time)))
        doctor.schedule.append(('do-admit', ([self], self.model.admission_time)))
        nurse.schedule.append(('do-document',([self.model.space.nurse_station],self.model.review_time)))

    def start_nurse_shift(self):
        # activities when starting a shift
        self.schedule.append(('do-medicine-check', ([self.model.space.medication_station], self.model.check_medicine_cart_time)))
        self.schedule.append(('do-document-risk', ([self.model.space.nurse_station], self.model.review_time)))

    def transfer_workload(self, agentCreator):
        new_worker = self.model.add_PersonAgents(agentCreator, 1, self.model.space.nurse_station, do_shift_takeover=True)
        new_worker.schedule.extend(self.schedule)
        new_worker.patients.extend(self.patients)
    
    def set_cutoff_time(self):
        """Set time to stop being active."""
        if self.atype == 'patient':
            self.cutoff_time = self.model.schedule.steps + self.model.patient_stay_length
        elif self.atype == 'nurse' or self.atype=='doctor':
            self.cutoff_time = self.model.schedule.steps + self.model.shift_length
        else: raise NameError('AgentTypeNotDefined')

    def get_path (self, from_agent, to_agent):
        
        # start and finish geo-points
        start=from_agent.geometry.centroid; end=to_agent.geometry.centroid

        # try to load path from cache
        for path_bounds, path in self.model.cache_paths.items():
            if self.model.space.compare_path_bounds(path_bounds, start, end): return path.tolist()

        # if not on cache: calculate shortest path
        found_path, stepByStep_Path = self.model.dstarlite.main(start, end)
        if not found_path: raise NameError ('path not found from %s to %s'%(str(start),str(end)))
        
        # update cache of paths
        self.model.cache_paths[(start,end)] = stepByStep_Path
        self.model.cache_paths[(end,start)] = stepByStep_Path[::-1]
        with open("data/paths/cache_paths.pkl", "wb") as cache_file:
            pickle.dump(self.model.cache_paths,cache_file)

        return stepByStep_Path.tolist()

    def link_paths(self,agents_to_visit):
        """Link paths to each agent."""
        start=self; end=agents_to_visit[0]
        self.path = self.get_path(start, end)
        for location in agents_to_visit[1:]:
            self.path += self.get_path(end, location)
            end=location

    def remove(self):
        """Remove agent from model and space."""
        if self.atype=='patient': # if patient, remove and trigger next patient's arrival
            self.model.schedule.patient_arrivals.append(self.model.schedule.steps + int(self.model.time_between_patients))
        elif self.atype=='nurse': # if nurse, remove and trigger replacement on next shift
            self.transfer_workload(self.model.ac_nurses)
            self.model.nurses.remove(self)
        elif self.atype=='doctor':
            self.transfer_workload(self.model.ac_doctors)
            self.model.doctors.remove(self)
        self.model.schedule.remove(self)
        self.model.space.remove_agent(self) 

    def count_agents(self):
        """Count agents in the model."""
        self.model.counts[self.state] += 1
        self.model.counts[self.atype] += 1