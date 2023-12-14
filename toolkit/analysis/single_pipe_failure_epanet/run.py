import wntr
import sys
import numpy as np
import matplotlib.pyplot as plt
import json
import os
from scipy.stats import rankdata
import pandas as pd
import time

def run(epanet_inp_path, param_dict, output_dir):
    start_time = time.time()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a water network model
    inp_file = epanet_inp_path
    wn = wntr.network.WaterNetworkModel(inp_file)
    
    # Simulation Options for criticality analysis
    analysis_end_time = param_dict['duration']
    wn.options.time.duration = analysis_end_time
    wn.options.hydraulic.demand_model = "DD"
    wn.options.hydraulic.required_pressure = param_dict['required_pressure']
    wn.options.hydraulic.minimum_pressure = 0
    
    # Create a list of pipes with defined diameter to include in the analysis
    pipes = wn.query_link_attribute("diameter", np.greater_equal, param_dict['min_diameter'], link_type=wntr.network.model.Pipe)
    pipes = list(pipes.index)
    #wntr.graphics.plot_network(wn, link_attribute=pipes, title='Pipes included in criticality analysis')
    #plt.show()
    
    # Define pressure threshold
    pressure_threshold = param_dict['pressure_threshold'] # usually same as pt_abnormal
    pressure_threshold_abnormal = param_dict['pressure_threshold_abnormal'] # usually same as pt_normal, but always pt_normal >= pt_abnormal
    
    # Run a preliminary simulation to determine if junctions drop below threshold during normal condition
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='single_pipe_failure_epanet_normal_tmp')
    
    # Criticality analysis, closing one pipe for each simulation
    min_pressure = results.node['pressure'].loc[:,wn.junction_name_list].min()
    below_threshold_normal_conditions = set(min_pressure[min_pressure < pressure_threshold].index)
    
    junctions_impacted = {}
    demand_impacted = {}
    for pipe_name in pipes:
        print("Pipe:", pipe_name)
    
        wn.reset_initial_values()
    
        pipe = wn.get_link(pipe_name)
        act = wntr.network.controls.ControlAction(pipe, "status", wntr.network.LinkStatus.Closed)
    
        cond = wntr.network.controls.SimTimeCondition(wn, "=", "00:00:00")
        ctrl = wntr.network.controls.Control(cond, act)
        wn.add_control("close pipe " + pipe_name, ctrl)
    
        sim = wntr.sim.EpanetSimulator(wn)
    
        try:
            results = sim.run_sim(file_prefix='single_pipe_failure_epanet_alt_tmp')
        except Exception as e:
            #XXX: maybe not save, but works for now: important: we *have* to reset state (to have clean simulation environment)
            wn.remove_control("close pipe " + pipe_name)
            print(f'something went wrong when running EPANET simulation, continue ... [pipe = {pipe_name}]', e)
            continue
    
        # Extract te number of juctions that dip below the min. pressure threshold
        min_pressure = results.node["pressure"].loc[:, wn.junction_name_list].min()
        below_threshold = set(min_pressure[min_pressure < pressure_threshold_abnormal].index)
    
        # Remove the set of junctions that were below the pressure threshold during normal conditions
        junctions_impacted[pipe_name] = below_threshold - below_threshold_normal_conditions
        # Create List of junctions impacted by low pressure
        List_of_junctions_impacted = list(junctions_impacted[pipe_name])
        # Get base demands
        demand = results.node['demand']
        # Calculate demand that cannot be served
        demand_impacted[pipe_name] = demand.loc[analysis_end_time, List_of_junctions_impacted].sum() * 1000
    
        wn.remove_control("close pipe " + pipe_name)
    
    # Extract the number of junctions impacted by low pressure conditions fpr each pipe closure
    
    #number_of_junctions_impacted = dict([(k, len(v)) for k,v in junctions_impacted.items()])
    
    #wntr.graphics.plot_network(wn, link_attribute=demand_impacted, node_size=0, link_width=N1, title="Not delivered demand\nfor each pipe closure")
    #plt.show()
    
    # Create pipe ranking and getting the 5 most critical pipes 
    M_failure = dict(zip(demand_impacted.keys(), rankdata([-i for i in demand_impacted.values()], method='min')))

    junctions_impacted_lists = {}
    for key, val in junctions_impacted.items():
        junctions_impacted_lists[key] = list(val)

    junctions_impacted_path = output_dir + '/junctions_impacted.json'
    with open(junctions_impacted_path, 'w') as f:
        f.write(json.dumps(junctions_impacted_lists))

    demand_impacted_output = pd.DataFrame.from_dict(demand_impacted, orient="index")
    demand_impacted_output.to_csv("demand_impacted.csv", sep=';')
    
    print('Duration: {}'.format(time.time()-start_time))

    return None, False

