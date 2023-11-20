import mesa_geo as mg
from shapely.geometry import Point
from model.Schedulers import PersonScheduler

class PersonAgent(mg.GeoAgent):

    def __init__(self, unique_id, model, geometry, crs, agent_type):
        """Create a new Person agent."""
        super().__init__(unique_id, model, geometry, crs)
        self.atype = agent_type

        self.scheduler=PersonScheduler(self)
        self.set_idle()
        self.interacting_with = None
        
        self.life_span = 0
        self.medication_frequency = self.model.medicine_round_frequency
        self.initialize()
        self.count_agents()
    
    def __repr__(self):
        return "PersonAgent_"+str(self.unique_id)

    def set_idle(self):
        self.state='idle'
        self.path=[]

    def initialize(self):
        """Set time to stop being active and schedule initial actions."""
        if self.atype == 'patient':
            self.nurse=None; self.doctor=None
            self.scheduler.add_scheduled_task(action='remove', 
                                              execute_in=self.model.patient_stay_length)
            self.scheduler.add_scheduled_task(action='request-admission')
            self.scheduler.add_scheduled_task(action='request-evaluation', 
                                              freq=self.model.evaluation_frequency)
            self.scheduler.add_scheduled_task(action='request-medication', 
                                              freq=self.medication_frequency)
        
        elif self.atype == 'nurse':
            self.model.nurses.append(self)
            self.start_shift()
            self.scheduler.add_scheduled_task(action='do-inventory',
                                          route=[self.model.space.medication_station], 
                                          duration=self.model.inventory_time)
        elif self.atype=='doctor':
            self.model.doctors.append(self)
            self.start_shift()
        else: raise NameError('AgentTypeNotDefined')
    
    def count_agents(self):
        """Count agents in the model."""
        self.model.counts[self.state] += 1
        self.model.counts[self.atype] += 1

    def start_shift(self):
        self.scheduler.add_scheduled_task(action='remove',
                                          execute_in=self.model.shift_length)
        self.patients=[]
        self.scheduler.add_scheduled_task(action='do-informative-meeting',
                                          route=[self.model.space.nurse_station], 
                                          duration=self.model.shift_transfer_meeting_time)

    def step(self):
        """Advance one step"""
        self.scheduler.execute_schedule(self.model.schedule.steps)
        self.model.resample_variables()
        self.count_agents()
        self.life_span += 1

    def prepare_task(self, **kwargs):
        '''either hold the current task while walking or hold the next task while executing current'''
        route = kwargs['route'] if 'route' in kwargs else []
        if not route or self.compare_placement(route[-1]):
            action=kwargs['action']
            print('prepare to execute')
            self.state=self.model.action_state[action]
            self.scheduler.hold_next_action = kwargs['duration'] if 'duration' in kwargs else 1

            # trigger functions at the beginning of the task
            if action=='request-admission': 
                self.request_admission()
                self.nurse.scheduler.add_scheduled_task(action='do-admit',
                                                        route=[self], 
                                                        duration=self.model.admission_time)
            elif action=='request-evaluation':
                self.doctor.scheduler.add_scheduled_task(action='do-evaluate',
                                                         route=[self], 
                                                         duration=self.model.evaluation_time)
                self.doctor.scheduler.add_scheduled_task(action='do-document',
                                                         route=[self.model.space.nurse_station], 
                                                         duration=self.model.evaluation_time)
            elif action=='request-medication':
                self.nurse.scheduler.add_scheduled_task(action='do-medicate',
                                                        route=[self], 
                                                        duration=self.medication_frequency)
                self.nurse.scheduler.add_scheduled_task(action='do-document',
                                                         route=[self.model.space.nurse_station], 
                                                         duration=self.model.evaluation_time)
            elif action in ['do-admit','do-evaluate', 'do-medicate']: 
                self.do_interactions(with_=route[-1], mode="initiate")
        
        else:
            print('prepare to walk')
            self.link_paths(route)
            self.state='walking'
            self.scheduler.hold_current_action = True # hold current task while walking

    def request_admission(self):
        # assign to doctor & nurse with least patients
        doctor=sorted(self.model.doctors, key=lambda doc: len(doc.patients))[0]
        nurse=sorted(self.model.nurses, key=lambda nurse: len(nurse.patients))[0]
        nurse.patients.append(self); doctor.patients.append(self)
        self.doctor=doctor; self.nurse=nurse
        
        
    def compare_placement(self, other_agent, radious=0.2) -> bool:
        """Return True if the agent is within radious of the other_agent"""
        return self.geometry.centroid.within(other_agent.geometry.centroid.buffer(radious))
    
    def link_paths(self, agents_to_visit):
        """Link paths to multiple agents"""
        start=self; end=agents_to_visit[0]
        self.path = self.model.space.get_path(start, end)
        for location in agents_to_visit[1:]:
            self.path += self.model.space.get_path(end, location)
            end=location
    
    def do_interactions(self, with_=None, mode=None):
        if mode=="initiate" and isinstance(with_, PersonAgent):
            print("initiate interaction")
            self.interacting_with=with_
            with_.interacting_with=self
            if self.state=='admitting': with_.state='in-admission'
            if self.state=='evaluating': with_.state='in-evaluation'
            if self.state=='medicating': with_.state='in-medication'
        
        elif mode=="terminate" and isinstance(self.interacting_with, PersonAgent):
            print("terminate interaction")
            if self.state=='admitting':
                self.interacting_with.state='admitted'
            if self.state=='evaluating':
                self.interacting_with.state='evaluated'
            if self.state=='medicating':
                self.interacting_with.state='medicated'
            self.interacting_with.interacting_with=None
            self.interacting_with=None

    def execute_task(self):
        if self.state=='walking':
            print('walking')
            for _ in range(self.model.walking_speed):
                self.geometry = Point(self.path.pop(0))
                if len(self.path)==0: 
                    self.scheduler.do_finish_task = True
                    break

        elif 'waiting' in self.state or self.state in ['in-admission', 'in-evaluation', 'in-medication']:
            print('waiting or receiving care')
            self.scheduler.hold_next_action = 1

        elif self.state=='leaving':
            self.scheduler.do_finish_task=True

        else:
            print('executing task')
            self.scheduler.hold_next_action -= 1
            if self.scheduler.hold_next_action <= 0: self.scheduler.do_finish_task=True
        
    def terminate_task(self):
        if self.state=='walking':
            print("arrived at destination")
            self.scheduler.hold_current_action=False
            self.set_idle()
        
        elif self.state=='leaving':
            print('removing')
            self.remove()

        else:
            print('finished task')
            self.do_interactions(mode="terminate")
            self.set_idle()
        
    def remove(self):
        """Remove agent from model and space."""
        # if patient, remove and trigger next patient's arrival
        if self.atype=='patient': 
            self.doctor.patients.remove(self)
            self.nurse.patients.remove(self)
            self.model.schedule.patient_arrivals.append(self.model.schedule.steps + int(self.model.time_between_patients))
        # if other, remove and trigger replacement on next shift
        elif self.atype=='nurse': 
            self.transfer_workload(self.model.ac_nurses)
            self.model.nurses.remove(self)
        elif self.atype=='doctor':
            self.transfer_workload(self.model.ac_doctors)
            self.model.doctors.remove(self)
        self.model.schedule.remove(self)
        self.model.space.remove_agent(self)

    def transfer_workload(self, agentCreator):
        new_worker = self.model.add_PersonAgents(agentCreator, 1, self.model.space.nurse_station, do_shift_takeover=True)
        new_worker.scheduler.task_queue.extend(self.scheduler.task_queue)
        new_worker.patients.extend(self.patients)
        for patient in self.patients:
            if patient.nurse==self: patient.nurse=new_worker
            elif patient.doctor==self: patient.doctor=new_worker