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

import pandas as pd  # For data manipulation (optional)

import epanet_util as enu

def run(epanet_inp_path):
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
    results = sim.run_sim()
    total_demand = results.node['demand'][junction_names].sum(axis=1)
    total_demand = total_demand[0]
   

     



    # Closing each valve and delocating it by closing valves in the segemnt and ones in the adjoining segment 

    for valve_id in valve_names:

        # list of segemnts closed already
        
        list_keys_closed = []

        # iteration over the segemnts

        for key, values in segment_valves_map_vlist.items():

            # closing the segments            

            if valve_id in values['valves']:
                
                for closing_valves in values['valves']:

                    # closing the affected segemnts

                    wn.get_link(closing_valves).initial_status = 'CLOSED'

                    # Get the valve from the network
                    valve_info = wn.get_link(closing_valves)
                    # Get the start and end nodes of the valve
                    start_node = valve_info.start_node_name
                    end_node = valve_info.end_node_name

                    if key in list_keys_closed:

                        continue

                    else:

                        list_keys_closed.append(key)

                    
                    # closing the adjoining segements                
                                 
                    
                    for key_1, values_1 in segment_valves_map_vlist.items():

                        if key_1 in list_keys_closed:

                            break

                        else:

                            if start_node in values_1 ['nodes']:

                                for closing_values_1 in values_1['valves']:

                                    wn.get_link(closing_values_1).initial_status = 'CLOSED'

                                list_keys_closed.append(key_1)
                                
                                    

                    
                            if end_node in values_1 ['nodes']:

                                for closing_values_1 in values_1['valves']:

                                        wn.get_link(closing_values_1).initial_status = 'CLOSED'

                                list_keys_closed.append(key_1)
                                        
                                        
                                


        

        # Run the simulation
        wn.options.hydraulic.demand_model = 'PDD'
        wn.options.time.duration = 1
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()

        
        # Calculate the total demand supplied during the simulation
        demand_supplied_all = results.node['demand'][junction_names].sum(axis=1)
        demand_supplied = demand_supplied_all[0]
        Difference_demand = (total_demand-demand_supplied)*1000 # 1000 to convert to l/sec

        #total_percenatge_missed = (Diff/total_demand)*100

        hydraulic_results[valve_id] = Difference_demand#, total_percenatge_missed # results show the amount of demand not supplied

        #reset initial valves, ie get all valves to original conditions 

        wn.reset_initial_values()
        wn = wntr.network.WaterNetworkModel(epanet_inp_path)

    
    # Convert the dictionary to a DataFrame
    df = pd.DataFrame(list(hydraulic_results.values()), index=hydraulic_results.keys(), columns=['Diff'])

    # Save the DataFrame to an Excel file
    df.to_excel('hydraulic_results.xlsx', index_label='Valve_ID')


    

    
# sending it into the function 

original_epanet_file = '1.Schwaz_20230529.inp'
run(original_epanet_file)
