import sys
import numpy as np
from platform import node
from turtle import clear, color
import json
from itertools import cycle
import networkx as nx
import pandas as pd
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

import pandas as pd  # For data manipulation (optional)

import epanet_util as enu

def run(epanet_inp_path, param_dict, output_dir):
    start_time = time.time()

    # segmentation program from uli

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

    
    hydraulic_results = {}

    # Create a water network model         

    wn = wntr.network.WaterNetworkModel(epanet_inp_path)

    # finding junction and valve lists

    junction_names = wn.junction_name_list  

    valve_names = wn.valve_name_list

    # Run the simulation and finding the total demand fulfilled during normal conditions 
    wn.options.hydraulic.demand_model = 'PDD'
    wn.options.time.duration = 1
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='valve_criticalit_a')
    total_demand = results.node['demand'][junction_names].sum(axis=1)
    total_demand = total_demand[0]

    total_demand_supplied_list = results.node['demand'][junction_names]
   
    # Closing each valve and delocating it by closing valves in the segemnt and ones in the adjoining segment 
    out_dict = {}


    for valve_id in valve_names:
        # list of segemnts closed already
        wn.get_link(valve_id).initial_status = 'CLOSED'
        
        list_keys_closed = []
        
    
        # Get the valve from the network
        valve_info = wn.get_link(valve_id)
        # Get the start and end nodes of the valve
        start_node = valve_info.start_node_name
        end_node = valve_info.end_node_name
    
        for key_1, values_1 in segment_valves_map_vlist.items():
            if start_node in values_1['nodes']:
                for closing_values_1 in values_1['valves']:
                    wn.get_link(closing_values_1).initial_status = 'CLOSED'

                list_keys_closed.append(key_1)

            elif end_node in values_1['nodes']:
                for closing_values_1 in values_1['valves']:
                    wn.get_link(closing_values_1).initial_status = 'CLOSED'
    
                list_keys_closed.append(key_1)

        # Run the simulation
        wn.options.hydraulic.demand_model = 'PDD'
        wn.options.time.duration = 1
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim(file_prefix='valve_criticalit_b')

        
        # Calculate the total demand supplied during the simulation
        demand_supplied_all = results.node['demand'][junction_names].sum(axis=1)
        demand_supplied = demand_supplied_all[0]
        Difference_demand = (total_demand-demand_supplied)*1000 # 1000 to convert to l/sec

        #total_percenatge_missed = (Diff/total_demand)*100

        hydraulic_results[valve_id] = Difference_demand#, total_percenatge_missed # results show the amount of demand not supplied

        #reset initial valves, ie get all valves to original conditions 
        demand_supplied_list = results.node['demand'][junction_names]

        list_demand_failed = []
        list_of_segment_nodes = []

        for junction, demand in total_demand_supplied_list.items():

            demand_node_failed = demand[0] - demand_supplied_list[junction][0]

            if (demand_node_failed > 0):
                list_demand_failed.append(junction)

        # total nodes in the segemnt
        for item in list_keys_closed:
            list_of_segment_nodes.append(segment_valves_map_vlist[item]['nodes'])

        flattened_list_segment_nodes = [item for sublist in list_of_segment_nodes for item in sublist]

        flattened_list_with_demands = []
        # to find demand nodes inside the main segment
        for items in flattened_list_segment_nodes:
            node_info = wn.get_node(items)
            if node_info.node_type == 'Junction':
                if node_info.base_demand > 0:
                    flattened_list_with_demands.append(items)

        # removing overlapping nodes to find the other indirect nodes

        indirect_nodes = []
        for item in list_demand_failed:
            if item in flattened_list_segment_nodes:
                continue
            else:
                indirect_nodes.append(item)

        print(valve_id, len(list_keys_closed))
        valve_entry = {
            "diff_demand": Difference_demand,
            "segment_id_a": list_keys_closed[0],
            "segment_id_b": list_keys_closed[1] if len(list_keys_closed) == 2 else list_keys_closed[0],
            "direct_demand_nodes": flattened_list_with_demands,
            "indirect_demand_nodes": indirect_nodes,
        }

        wn.reset_initial_values()
        wn = wntr.network.WaterNetworkModel(epanet_inp_path)

        out_dict[valve_id] = valve_entry
    
    # Convert the dictionary to a DataFrame
    df = pd.DataFrame(list(hydraulic_results.values()), index=hydraulic_results.keys(), columns=['Diff'])

    # Save the DataFrame to an Excel file
    df.to_excel('hydraulic_results.xlsx', index_label='Valve_ID')

    #{
    #    "valve_id": {
    #        "demand_diff": ...
    #        "neighb_a": 
    #        "neighb_b": ..
    #        "direct_list_of_segment_nodes": 
    #        "indirect_list_of_segment_nodes": 
    #    }
    #}

    output_path = output_dir + '/out.json'
    with open(output_path, 'w') as f:
        f.write(json.dumps(out_dict))

    return None, False

# sending it into the function 
#original_epanet_file = '1.Schwaz_20230529.inp'
#run(original_epanet_file)

