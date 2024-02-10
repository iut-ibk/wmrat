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
    wn.options.hydraulic.demand_model = "PDD"
    wn.options.hydraulic.required_pressure = param_dict['required_pressure']
    wn.options.hydraulic.minimum_pressure = 0

    junction_names = wn.junction_name_list

    # Create a list of pipes with defined diameter to include in the analysis
    pipes = wn.query_link_attribute("diameter", np.greater_equal, param_dict['min_diameter'], link_type=wntr.network.model.Pipe)
    pipes = list(pipes.index)
    
    # Define pressure threshold
    pressure_threshold = param_dict['pressure_threshold'] # usually same as pt_abnormal
    pressure_threshold_abnormal = param_dict['pressure_threshold_abnormal'] # usually same as pt_normal, but always pt_normal >= pt_abnormal
    
    # Run a preliminary simulation to determine if junctions drop below threshold during normal condition
    sim = wntr.sim.EpanetSimulator(wn)
    #results = sim.run_sim(file_prefix='segment_criticality_normal_tmp')

    results = sim.run_sim()
    total_demand = results.node['demand'][junction_names].sum(axis=1)
    total_demand = total_demand[0]

    total_demand_supplied_list = results.node['demand'][junction_names]
    
    # Criticality analysis, closing valves for each simulation
    min_pressure = results.node['pressure'].loc[:,wn.junction_name_list].min()
    below_threshold_normal_conditions = set(min_pressure[min_pressure < pressure_threshold].index)
    
    for segment_id, segment_info in segment_valves_map_vlist.items():
        valves = segment_info['valves']
        print('segment: ', segment_id)
        print('valves: ', valves)
        print('---')
    
        #wn.reset_initial_values()
        wn_copied = copy.deepcopy(wn)

        for valve_name in valves:
            valve = wn_copied.get_link(valve_name).initial_status = 'CLOSED'
            #act = wntr.network.controls.ControlAction(valve, "status", wntr.network.LinkStatus.Closed)
    
            #cond = wntr.network.controls.SimTimeCondition(wn, "=", "0:00:00")
            #ctrl = wntr.network.controls.Control(cond, act)
            #wn.add_control("close valve " + valve_name, ctrl)
    
        sim = wntr.sim.EpanetSimulator(wn_copied)

        results = sim.run_sim()

        # Calculate the total demand supplied during the simulation
        demand_supplied_all = results.node['demand'][junction_names].sum(axis=1)
        demand_supplied = demand_supplied_all[0]
        Difference_demand = (total_demand-demand_supplied)*1000

        name = f'wntr_{segment_id}.inp'
        wntr.network.write_inpfile(wn_copied, name)
    
        try:
            results = sim.run_sim(file_prefix='segment_criticality_alt_tmp')
        except Exception as e:
            #XXX: maybe not save, but works for now: important: we *have* to reset state (to have clean simulation environment)
            #wn.remove_control("close valve " + valve_name)
            #for valve_name in valves:
            #    wn.remove_control("close valve " + valve_name)

            print(f'something went wrong when running EPANET simulation, continue ... [segment = {segment_id}]', e)
            continue
    
        # Extract te number of juctions that dip below the min. pressure threshold
        min_pressure = results.node["pressure"].loc[:, wn_copied.junction_name_list].min()
        below_threshold = set(min_pressure[min_pressure < pressure_threshold_abnormal].index)
    
        # Remove the set of junctions that were below the pressure threshold during normal conditions
        junctions_impacted_set = below_threshold - below_threshold_normal_conditions
        
        print('min_pressure', min_pressure)

        list_of_segment_nodes = segment_valves_map_vlist[segment_id]['nodes']

        list_demand_direct_nodes = []

        for items in list_of_segment_nodes:
            node_info = wn.get_node(items)
            if node_info.node_type == 'Junction':
                if node_info.base_demand > 0:
                    list_demand_direct_nodes.append(items)

        demand_supplied_list = results.node['demand'][junction_names]

        list_demand_failed = []

        for junction, demand in total_demand_supplied_list.items():

            demand_node_failed = demand[0] - demand_supplied_list[junction][0]

            if (demand_node_failed > 0):
                list_demand_failed.append(junction)

        print(list_demand_failed)

        # removing overlapping nodes to find the other isolated nodes
        isolated_nodes = []
        for item in list_demand_failed:
            if item not in list_demand_direct_nodes:
                isolated_nodes.append(item)

        segment_valves_map_vlist[segment_id]['diff_demand'] = Difference_demand

        segment_valves_map_vlist[segment_id]['direct'] = list_demand_direct_nodes
        segment_valves_map_vlist[segment_id]['indirect'] = isolated_nodes
    
        #for valve_name in valves:
        #    wn.remove_control("close valve " + valve_name)
    
    # write results with segment infos
    segment_json_path = output_dir + '/junctions_impacted.json'
    with open(segment_json_path, 'w') as f:
        f.write(json.dumps(segment_valves_map_vlist))

    print('Duration: {}'.format(time.time()-start_time))

    return None, False

