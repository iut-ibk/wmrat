#####   © Martin Oberascher and Rahul (2022)  #####

# Related files: EBCQ_functions.py, graph_editing.py, misc_light.py

import networkx as nx
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import math
import copy
from scipy.stats import rankdata
import time
import misc_light
import graph_editing
import EBCQ_functions_Jilin
import itertools
import hydraulics_validation
import collections
import pickle
import Data_reading
import random
import sys
import wntr
import csv

def run(epanet_inp_path, param_dict, output_dir):
    
    start_time_H = time.time()
    
    # Open a water network model, Creating graph
    inp_file = epanet_inp_path
    n_combs = param_dict['n_combs']
    
    f = open(inp_file)
    success, val = misc_light.swmm_input_read(f)
    network_graph = graph_editing.create_graph_of_epanet_file(val)
    
    # Getting postion and other parameters with get attributes
    
    pos= nx.get_node_attributes(network_graph, 'pos')
    demands = nx.get_node_attributes(network_graph, 'demand')
    total_demand = sum(demands.values())
    weights = nx.get_edge_attributes(network_graph, 'Wei')
    name = nx.get_edge_attributes(network_graph, 'key')
    elevation = nx.get_node_attributes(network_graph, 'elevation')
    
    print(elevation)
    
    #if "28" in elevation:
    #    node_elevation = elevation["28"]
    
    #if "1" in elevation:
    #   reservoir_elevation = elevation ["1"]
    
    C_max = nx.get_edge_attributes(network_graph, 'dia')
    total_demand = sum(demands.values())
    length_links = nx.get_edge_attributes(network_graph, 'len')
    
    
    # Solve the pressure-driven analysis
    wn = wntr.network.WaterNetworkModel(inp_file)
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='multi_graph_normal_tmp')
    
    
    friction_factors = {}
    
    # Extract the friction factor for each pipe and calcualtion of head differnece
    
    
    #for link_name, link in wn.links.items():
    #
    #    start_node = wn.get_link(link_name).start_node
    #    end_node = wn.get_link(link_name).end_node
    #    
    #    # Calculate the mid-elevation
    #
    #    if (start_node.name == '28'):
    #    
    #       mid_elevation = abs(end_node.elevation)
    #
    #    elif (end_node.name == '28'):
    #
    #        mid_elevation = abs(start_node.elevation)
    #
    #    #elif (end_node.name == '1'):
    #
    #    #    mid_elevation = abs(start_node.elevation - reservoir_elevation)
    #
    #    else:
    #
    #        mid_elevation = node_elevation - (start_node.elevation)
    #
    #
    #
    #
    #    if isinstance(link, wntr.network.Pipe):
    #        friction_factor = results.link['friction_factor'].loc[:, link_name].mean()
    #        friction_factors[link_name] = friction_factor, mid_elevation
    #
        
    
    
    
    #saving friction loss and head loss
    
    #
    #C_max_F = {(wn.get_link(key).start_node_name, wn.get_link(key).end_node_name): items for key, items in friction_factors.items()}
    #
    #C_max_F_R = {keys[::-1]: value for keys, value in C_max_F.items()}
    #
    #
    #v ={}
    #
    ## calculation of v 
    #
    #for key, value in C_max.items():
    #
    #    if key in C_max_F.keys():
    #
    #        if C_max_F[key][0] == 0:
    #
    #            v[key] = 3
    #
    #        else:
    #
    #            
    #            v[key] = math.sqrt((2*9.81* C_max[key])/ (C_max_F[key][0]*1000*length_links[key]))
    #
    #    elif key in C_max_F_R.keys():
    #
    #        if C_max_F_R[key][0] == 0:
    #
    #            v[key] = 3
    #
    #        else:
    #
    #            v[key] = math.sqrt((2*9.81* C_max[key])/ (C_max_F_R[key][0]*1000*length_links[key]))
    #
    #
    #
    #
    
    
    # C calcualtion
    
    # because EPANET uses mm^3/sec => l/s
    C_max.update((key, value * value / 4000000 * math.pi *3* 1000) for key, value in C_max.items())
    
    
    
    
    
    # getting node demands for EBCQ
    
    K = dict((k, v) for k, v in demands.items() if float(v) >= 0)
    
    # Shortest path from (multiple) sources
    # Creating dict L with edges
    
    #SP = nx.multi_source_dijkstra_path(network_graph, sources={'28'}, weight='Wei')  #'HB_Pirchanger', 'HB_Schmadl', 'HB_Pertrach', 
    SP = nx.multi_source_dijkstra_path(network_graph, sources={'HB_Kraken'}, weight='Wei')  #'HB_Pirchanger', 'HB_Schmadl', 'HB_Pertrach', 
    L = dict()
    L.update(dict.fromkeys(network_graph.edges(), 0.0))
    
    # Demand Edge Betweenness Centrality
    
    EBCQ_normal = EBCQ_functions_Jilin.EBCQ(SP, L, K)
    
    EBCQ_normal_R = {keys[::-1]: value for keys, value in EBCQ_normal.items()}
    
    
    
    
    
    # total bridges in the network
    
    res_bridges = list (nx.bridges(network_graph))
    
    
    
    ########################combinations###############################################
    
    
    edges_b = list(network_graph.edges())
    edges_all = list(network_graph.edges())
    
    for edge in edges_b[:]:  # iterate over a copy of edges_b
        if edge in res_bridges:
            edges_b.remove(edge)
    
    
    
    # combinations = Combinations.Combinations(edges_b, network_graph)
    
    #Combination_list = [tuple(v) for v in combinations]
    
    #with open('combinations.pkl', 'rb') as f:
     #   combinations = pickle.load(f)
    
    #Combination_list = [tuple(v) for v in combinations]
    
    combi = 2
    
    correlation = {}
    
    #c = int(input("Enter the number of combinations you want: "))
    c = n_combs
    
    
    
    
    #############getting the combinations
    
    while (combi <= c):
    
        #reservoir_size = 20000
        selected_combinations = []
    
        ### for n numeber of combiantions use this code for large networks
    
        #for i, combination in enumerate(itertools.combinations(edges_b, combi)):
        #    if i < reservoir_size:
        #        selected_combinations.append(combination)
    
                
        #    else:
        #        j = random.randint(0, i)
        #        if j < reservoir_size:
        #            selected_combinations[j] = combination
    
        
        #combination = (itertools.combinations(edges_b, combi))
    
        selected_combinations = list(itertools.combinations(edges_b, combi))
    
    
        length_total = len(selected_combinations)
    
            
        
    
    
                        
    
    
        
    
    
    
    
    
    
        ##########################multiple EBCQ############################################################  
    
        #start_time_G = time.time()
    
    
        Failure_EBCQ_multiple = dict.fromkeys(selected_combinations, 0) #list(map(dict, itertools.combinations(L.items(), 2)))
    
        Failure_EBCQ_multiple = EBCQ_functions_Jilin.Failure_EBCQ_multiple(EBCQ_normal, EBCQ_normal_R, network_graph, K, Failure_EBCQ_multiple, C_max)
    
        
    
        #end_time_G = time.time()
    
        #runtime_G = end_time_G - start_time_G
    
        ###finding the length of set and top 5%
    
        length_set = len(Failure_EBCQ_multiple)
    
        #length_it = round((length_set/100)*5)
        
    
    
        # sorting
    
        sorted_dict_EBCQ = dict(sorted(Failure_EBCQ_multiple.items(), key=lambda item: item[1], reverse=True))
    
        #sorted_dict_EBCQ = dict(itertools.islice(sorted_dict_EBCQ.items(), 1000))   
    
        count_less_than_zero = sum(1 for value in Failure_EBCQ_multiple.values() if value <= 0)
    
        sorted_dict_EBCQ = {key: value for key, value in sorted_dict_EBCQ.items() if value > 0}
    
    
        
    
    
        ##############################df = pd.DataFrame(sorted_dict_EBCQ.items(), columns=['Key', 'Value'])
    
        ###############################output = str(combi) + 'output.xlsx'
    
        # Save the DataFrame as an Excel file
        ###############################df.to_excel(output, index=False)    
    
    
        results_Graph = list(sorted_dict_EBCQ.keys())
    
    
        # Creating dict M with ranking of pipe importance
        # Adding Failure_EBCQ to edge attributes
    
        #M_failure = dict(zip(sorted_dict_EBCQ.keys(), rankdata([-i for i in sorted_dict_EBCQ.values()], method='min')))
    
        #saving EBCQ values 
    
        #with open("EBCQ_values.pkl", "wb") as f:
        #        pickle.dump(Failure_EBCQ_multiple, f)
    
    
        # combiantions rank sorting and saving
    
        #sorted_dict = dict(sorted(sorted_dict_EBCQ.items(), key=lambda item: item[1]))
    
       
        # saving Ranks 
    
    
        #with open("Rank_Graph.pkl", "wb") as f:
        #        pickle.dump(sorted_dict, f)
    
    
        ### hydraulic comaprispn ######################
    
    
    
        top20_hydra = {}
        sorted_dict_G = {}
    
    
        i = 0
        ### converting to pipe names for hydraulic comparison
    
          
        for key, items in sorted_dict_EBCQ.items():
    
            values_hydra = []
    
            for j in range(len(key)):
                
                u = results_Graph[i][j][0]
                v = results_Graph[i][j][1]
    
                
                edge_data = network_graph.get_edge_data(u, v)
    
                edge_key = edge_data['key']
    
                values_hydra.append(edge_key)
    
                j = j + 1
    
            
            top20_hydra [i] = values_hydra
            i = i + 1
            pipe_name_tuple = tuple(values_hydra)
            sorted_dict_G[pipe_name_tuple] = items    
                
               
    
    
        
       
    
        results_hydraulic= hydraulics_validation.hydraulics_validation(inp_file, top20_hydra)
    
        #end_time_H = time.time()
    
        #runtime_H = end_time_H - start_time_H
    
        
        #M_failure_H = dict(zip(results_hydraulic.keys(), rankdata([-i for i in results_hydraulic.values()], method='min')))
    
    
        sorted_dict_H = results_hydraulic
        sorted_dict_H = {key: max(value, 0) for key, value in sorted_dict_H.items()}
        
    
    
    
        
        Data_reading.dataview(sorted_dict_G,sorted_dict_H, combi, count_less_than_zero, length_total)    
    
        combi = combi + 1
    
    
    end_time_H = time.time()
    
    runtime_H = end_time_H - start_time_H
    
    print(runtime_H)

