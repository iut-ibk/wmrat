from copy import deepcopy
import sys
import numpy as np
from platform import node
#from turtle import clear, color
import json
from itertools import cycle
import networkx as nx
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
from matplotlib import cm
import math
import copy
from collections import Counter
from collections import OrderedDict
from operator import itemgetter, truediv
from scipy.stats import rankdata
import misc_light
import graph_editing
import os
from numpy import log as ln
import time
import wntr

import epanet_util as enu

def run(epanet_inp_path, param_dict, output_dir):
    start_time = time.time()

    success, val = enu.epanet_inp_read(epanet_inp_path)
    if not success:
        return False #XXX

    epanet_dict = val

    success, val = enu.epanet_to_graph(epanet_dict)
    if not success:
        return False #XXX

    graph = val

    nodes, edges = graph

    segment_valves_map = enu.epanet_segments_via_valves(nodes, edges)

    # list -> set
    segment_valves_map_vlist = {}
    for k, v in segment_valves_map.items():
        entry = {
            'nodes': list(v['nodes']),
            'valves': list(v['valves']),
            'edges': list(v['edges']),
        }
        segment_valves_map_vlist[k] = entry

    # Create a water network model
    wn = wntr.network.WaterNetworkModel(epanet_inp_path)
    
    # Simulation Options for criticality analysis
    analysis_end_time = param_dict['duration']
    wn.options.time.duration = analysis_end_time
    wn.options.hydraulic.demand_model = "DD"
    wn.options.hydraulic.required_pressure = param_dict['required_pressure']
    wn.options.hydraulic.minimum_pressure = 0
    
    # Create a list of pipes with defined diameter to include in the analysis
    pipes = wn.query_link_attribute("diameter", np.greater_equal, param_dict['min_diameter'], link_type=wntr.network.model.Pipe)
    pipes = list(pipes.index)
    
    # Define pressure threshold
    pressure_threshold = param_dict['pressure_threshold'] # usually same as pt_abnormal
    pressure_threshold_abnormal = param_dict['pressure_threshold_abnormal'] # usually same as pt_normal, but always pt_normal >= pt_abnormal
    
    # Run a preliminary simulation to determine if junctions drop below threshold during normal condition
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='segment_criticality_normal_tmp')
    
    # Criticality analysis, closing valves for each simulation
    min_pressure = results.node['pressure'].loc[:,wn.junction_name_list].min()
    below_threshold_normal_conditions = set(min_pressure[min_pressure < pressure_threshold].index)
    
    for segment_id, segment_info in segment_valves_map_vlist.items():
        valves = segment_info['valves']
        print('segment: ', segment_id)
        print('valves: ', valves)
        print('---')
    
        wn.reset_initial_values()

        for valve_name in valves:
            valve = wn.get_link(valve_name)
            act = wntr.network.controls.ControlAction(valve, "status", wntr.network.LinkStatus.Closed)
    
            cond = wntr.network.controls.SimTimeCondition(wn, "=", "0:00:00")
            ctrl = wntr.network.controls.Control(cond, act)
            wn.add_control("close valve " + valve_name, ctrl)
    
        sim = wntr.sim.EpanetSimulator(wn)
    
        try:
            results = sim.run_sim(file_prefix='segment_criticality_alt_tmp')
        except Exception as e:
            #XXX: maybe not save, but works for now: important: we *have* to reset state (to have clean simulation environment)
            wn.remove_control("close valve " + valve_name)
            for valve_name in valves:
                wn.remove_control("close valve " + valve_name)

            print(f'something went wrong when running EPANET simulation, continue ... [segment = {segment_id}]', e)
            continue
    
        # Extract te number of juctions that dip below the min. pressure threshold
        min_pressure = results.node["pressure"].loc[:, wn.junction_name_list].min()
        below_threshold = set(min_pressure[min_pressure < pressure_threshold_abnormal].index)
    
        # Remove the set of junctions that were below the pressure threshold during normal conditions
        junctions_impacted_set = below_threshold - below_threshold_normal_conditions
        segment_valves_map_vlist[segment_id]['junctions_impacted'] = list(junctions_impacted_set)
    
        for valve_name in valves:
            wn.remove_control("close valve " + valve_name)
    
    # write results with segment infos
    segment_json_path = output_dir + '/junctions_impacted.json'
    with open(segment_json_path, 'w') as f:
        f.write(json.dumps(segment_valves_map_vlist))

    print('Duration: {}'.format(time.time()-start_time))

    return None, False

