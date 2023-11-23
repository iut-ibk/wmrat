from copy import deepcopy
import sys
import numpy as np
from platform import node
from turtle import clear, color
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

#def run(epanet_inp_path, param_dict, output_dir):
#    start_time = time.time()
#
#    if not os.path.exists(output_dir):
#        os.makedirs(output_dir)
#
#    success, val = enu.epanet_inp_read(epanet_inp_path)
#    if not success:
#        return False #XXX
#
#    epanet_dict = val
#
#    #XXX: do not hard-code this ... when importing demand it from the user?
#    epanet_epsg_code = 31254
#
#    success, val = enu.epanet_to_graph(epanet_dict)
#    if not success:
#        return False #XXX
#
#    graph = val
#
#    nodes, edges = graph
#
#    #print('--- NODES ---')
#    #for k, v in nodes.items():
#    #    print(k, v)
#
#    #print('--- EDGES ---')
#    #for k, v in edges.items():
#    #    print(k, v)
#
#    print('nodes', len(nodes))
#    print('edges', len(edges))
#
#    G = nx.Graph()
#
#    for node, node_info in nodes.items():
#        G.add_node(node, x=node_info['coords'][0][0], y=node_info['coords'][0][1])
#
#    valves = dict()
#
#    for edge_name, edge_info in edges.items():
#        node1 = edge_info["node1"]
#        node2 = edge_info["node2"]
#
#        #XXX 
#        if edge_info['type'] != 'VALVE':
#            G.add_edge(node1, node2, name=edge_name)
#        else:
#            valves[edge_name] = edge_info
#
#    colors = cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
#
#    connected_components = list(nx.connected_components(G))
#
#    node_colors = {}
#    for i, component in enumerate(connected_components):
#        color = next(colors)
#        for node in component:
#            node_colors[node] = color
#
#    segment_valves_map = {}
#    for i, segment in enumerate(connected_components):
#        segment_valves_map[i] = {
#            'nodes': segment,
#            'valves': set(),
#        }
#
#        for valve, valve_info in valves.items():
#            if valve_info['node1'] in segment or valve_info['node2'] in segment:
#                segment_valves_map[i]['valves'].add(valve)
#
#    #print(type(G))
#
#    # Iterate over the connected components
#    for key, val in segment_valves_map.items():
#        print('segment', key)
#        print('info', val)
#        print('---')
#
#    # Print the number of nodes and edges
#    print('#nodes', len(G.nodes))
#    print('#edges', len(G.edges))
#
#    num_subgraphs = len(list(nx.connected_components(G)))
#    print('#connected components', num_subgraphs)
#
#    print(len(valves))
#
#    #print('avg', nx.average_node_connectivity(graph))
#
#    #pos = {node: (attrs['coords'][0][0], attrs['coords'][0][1]) for node, attrs in nodes.items()}
#    #nx.draw(G, pos, with_labels=False, font_weight='bold', node_size=10, node_color=[node_colors[node] for node in G.nodes])
#    #plt.show()
#    
#    return True

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
    results = sim.run_sim(file_prefix='segment_criticality_normal_tmp')
    
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
    
        cond = wntr.network.controls.SimTimeCondition(wn, "=", "24:00:00")
        ctrl = wntr.network.controls.Control(cond, act)
        wn.add_control("close pipe" + pipe_name, ctrl)
    
        sim = wntr.sim.EpanetSimulator(wn)
    
        try:
            results = sim.run_sim(file_prefix='segment_criticality_alt_tmp')
        except Exception as e:
            #XXX: maybe not save, but works for now: important: we *have* to reset state (to have clean simulation environment)
            wn.remove_control("close pipe" + pipe_name)
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
    
        wn.remove_control("close pipe" + pipe_name)
    
    # Extract the number of junctions impacted by low pressure conditions fpr each pipe closure
    
    #number_of_junctions_impacted = dict([(k, len(v)) for k,v in junctions_impacted.items()])
    
    N1 = list(dict.values(demand_impacted))
    int_ = 7
    N1 = [x / int_ for x in N1]
    N1 = [0.5 if x==0 else x for x in N1]
    
    #wntr.graphics.plot_network(wn, link_attribute=demand_impacted, node_size=0, link_width=N1, title="Not delivered demand\nfor each pipe closure")
    #plt.show()
    
    # Create pipe ranking and getting the 5 most critical pipes 
    M_failure = dict(zip(demand_impacted.keys(), rankdata([-i for i in demand_impacted.values()], method='min')))
    #Most_critical_pipes = sorted(M_failure, key=M_failure.get, reverse = False)[:5]
    #print('The Most Critcal Pipes are:', Most_critical_pipes)
    
    # rewrite values to int()
    #M_failure_int = {}
    #for key, val in M_failure.items():
    #    M_failure_int[key] = int(val)

    #demand_impacted_path = output_dir + '/links.json'
    #with open(demand_impacted_path, 'w') as f:
    #    f.write(json.dumps(M_failure_int))

    junctions_impacted_lists = {}
    for key, val in junctions_impacted.items():
        junctions_impacted_lists[key] = list(val)

    junctions_impacted_path = output_dir + '/junctions_impacted.json'
    with open(junctions_impacted_path, 'w') as f:
        f.write(json.dumps(junctions_impacted_lists))

    demand_impacted_output = pd.DataFrame.from_dict(demand_impacted, orient="index")
    demand_impacted_output.to_csv("demand_impacted.csv", sep=';')
    
    print('Duration: {}'.format(time.time()-start_time))

    return True

