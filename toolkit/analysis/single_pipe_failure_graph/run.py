from copy import deepcopy
import sys
from platform import node
from turtle import clear, color
import json
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

def run(epanet_inp_path, param_dict, output_dir):
    start_time = time.time()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Create a water network model (Anytown for faster analysis)
    f = open(epanet_inp_path)
    success, val = misc_light.swmm_input_read(f)
    network_graph = graph_editing.create_graph_of_epanet_file(val)
    
    # Getting position and otehr parameters with get attributes
    pos = nx.get_node_attributes(network_graph, 'pos')
    demands = nx.get_node_attributes(network_graph, 'demand')
    weights = nx.get_edge_attributes(network_graph, 'Wei')
    C_max = nx.get_edge_attributes(network_graph, 'dia')
    name = nx.get_edge_attributes(network_graph, 'key')
    elevation = nx.get_node_attributes(network_graph, 'elevation')

    # Calculating pressure losses
    hv = copy.deepcopy(weights)
    lam = float(param_dict['lambda'])
    hv.update((key, value * lam / (2 * 9.81)) for key, value in hv.items())
    Hv = {key: hv[key] / (C_max.get(key, 0)**2/4000000 * math.pi)**2 for key in hv}
    
    # Shortest path from multiple sources
    # Creating dict L with edges
    # Creating dict K by removing nodes with demand 0, when >0, removing Tanks from nodes
    SP = nx.multi_source_dijkstra_path(network_graph, sources=set(param_dict['sources']), weight='Wei')
    L = dict()
    L.update(dict.fromkeys(network_graph.edges(), 0.0))
    
    K = dict((k, v) for k, v in demands.items() if float(v) >= 0)       # >0: Nodes with demand 0 are not included; >=0: Nodes with demand 0 are included
    
    # Demand Edge Betweenness Centrality
    def EBCQ(SP, L, demand):
        for node, demand in K.items():
            #for node, path in SP.items():
            #print(node, path)
            path = SP[node]
            #if node in demands:
               # if float(demands[node]) > 0:
            if len(path) == 1:
                continue
            else:
                for i in range(len(path)-1):
                #print(path[i])
                    u = path[i]
                    v = path[i+1]
                    if(u, v) not in L:
                        L[(v, u)] += float(demand)              # EBCQ if float(1) -> EBC
                    else:
                        L[(u, v)] += float(demand)              # EBCQ if float(1) -> EBC
        return(L)
    
    L = EBCQ(SP, L, K)
    
    #print(L)
    
    # Calculating all pressure losses
    
    #Losses_all = {key: Hv[key] * (L.get(key, 0)/1000)**2 for key in Hv}
    
    #pressure_threshold = 14.00
    
    #Z = dict()
    #Z.update(dict.fromkeys(network_graph.nodes(), 0.0))
    
    #def EBCQP(SP, Z, Losses_all):
    #    for node, demand in K.items():
    #        path = SP[node]
    #        if len(path) == 1:
    #            continue
    #        else:
    #            for i in range(len(path)-1):
    #                u = path[i]
    #                v = path[i+1]
    #                if(u, v) not in Losses_all:
    #                   Z[node] += Losses_all.get((v, u), 0)
    #                else:
    #                    Z[node] += Losses_all.get((u, v), 0)
    #    return(Z)
    
    #Z = EBCQP(SP, Z, Losses_all)
    #Rel_Elevation = {key: elevation['1']- elevation.get(key, 0) for key in elevation}
    #Pressure_normal = {key: Rel_Elevation[key] - Z.get(key, 0) for key in Rel_Elevation}
        
    # Creating dict M with ranking of pipe importance
    # Adding EBCQ to edge attributes 
    M = dict(zip(L.keys(), rankdata([-i for i in L.values()], method='min')))
    nx.set_edge_attributes(network_graph, L, "EBCQ")
    
    # Defining edge colors according to weights; Colormap
    # Colormaps: https://matplotlib.org/stable/tutorials/colors/colormaps.html
    for u,v,d in network_graph.edges(data=True):
        d['EBCQ']
    
    edges,weights = zip(*nx.get_edge_attributes(network_graph,'EBCQ').items())
    cmap = mpl.colormaps['jet'] 
    
    # Calculating and rescaling edge width
    N = list(dict.values(L))
    _int = 7
    N = [x / _int for x in N]
    N = [0.5 if x<0.5 else x for x in N]
    
    # Plotting edges and nodes with color ramp
    L.update((key, round(val, 3)) for key, val in L.items())
    edge_labels = L

    #nodes = nx.draw_networkx_nodes(network_graph, pos=pos,node_size= 1.0, node_color='black')
    #edges = nx.draw_networkx_edges(network_graph, pos=pos,width=list(N), edge_color=weights, edge_cmap= cmap)
    
    #edges_Label=nx.draw_networkx_edge_labels(network_graph, pos, edge_labels= edge_labels)
    #ax = plt.gca()
    #ax.set_title('EBCQ Normal')
    
    #plt.colorbar(edges, shrink=0.5, pad=0)
    #plt.show()
    
    # Removing 0's from dict L          # create Deepcopy for furter analysis
    #copy for L und then loop
    EBCQ_normal = copy.deepcopy(L)
    
    for k in EBCQ_normal.copy():
       if EBCQ_normal[k] == 0.0:
        del EBCQ_normal[k]
    
    # Creating a new graph for iteration 
    Failure_EBCQ = dict()
    Failure_EBCQ.update(dict.fromkeys(network_graph.edges(), 0.0))
    
    # Calculating max flow capcacity; pumps are missing -> no dia -> no C_max
    x = 3.25
    def Velocity(dia):
        Velocity = 0.001 * x * dia + 0.6996 * x
        return Velocity
    C_max.update((key, value * value / 4000000 * math.pi * Velocity(value) * 1000) for key, value in C_max.items())       # C_max in l/s, when 4000000
    
    for edges in EBCQ_normal:
        print("Pipe:", edges)
        u = edges[0]
        v = edges[1]
        network_graph_2 = copy.deepcopy(network_graph)         
        if network_graph_2.has_edge(u, v):    
            network_graph_2.remove_edge(u, v) 
        else:
            network_graph_2.remove_edge(v, u)
    
        trail = nx.is_connected(network_graph_2)
    
        # if trail == False: EBCQ does not change; removed edge has no impact on EBCQ
        if trail == False:
            # L  
            Failure_EBCQ [(u,v)] = EBCQ_normal[(u,v)]                                                             # Key, lt. Martin: Failure EBCQ [(u,v)] = EBCQ1
        # Iteration after removing an edge; in C_max is edge 20, 10 missing -> pump -> no diameter -> no C_max  
        else:
            L1 = dict()
            L1.update(dict.fromkeys(network_graph_2.edges(), 0.0))
            SP_abnormal = nx.multi_source_dijkstra_path(network_graph_2, sources=set(param_dict['sources']), weight='Wei')
            EBCQ_abnormal = EBCQ(SP_abnormal, L1, K)                                                         # L2
            #EBCQ_delta = dict(set(EBCQ_abnormal.items())-set(L.items()))                                    # delta EBCQ
            # Keep only EBCQ_delta > 0
            # Compare with Qmax = Cmax                                  
            C_delta = {key: EBCQ_abnormal[key] - C_max.get(key, 0) for key in EBCQ_abnormal}               # Comparison delta C_max and EBCQ_delta
            Failure_EBCQ[(u, v)] = sum(v for v in C_delta.values() if v > 0)                               # Max: sum(v for v in C_delta.values() if v > 0); Min:sum(v for v in C_delta.values() if v < 0)
            
            #Losses_abnormal = {key: Hv[key] * (EBCQ_abnormal.get(key, 0)/1000)**2 for key in Hv}
            #Z1 = dict()
            #Z1.update(dict.fromkeys(network_graph_2.nodes(), 0.0))
            #Z1 = EBCQP(SP_abnormal, Z1, Losses_abnormal)
            #Pressure_abnormal = {key: Rel_Elevation[key] - Z1.get(key, 0) for key in Rel_Elevation} 
            #Y = dict((k, v) for k, v in Pressure_abnormal.items() if float(v) < pressure_threshold)
            #A = 0
            #for nodes in Y:
            #   A += demands.get(nodes, 0)
            #Failure_EBCQ[(u, v)] = A
            #a = 5                                                       # Max. wert: max(max(C_delta.values()),0)
    
    # Getting length of pathes and multiply it with hv to get pressure losses
    # Creating dict M with ranking of pipe importance
    # Adding EBCQ to edge attributes
    
    M_failure = dict(zip(Failure_EBCQ.keys(), rankdata([-i for i in Failure_EBCQ.values()], method='min')))
    nx.set_edge_attributes(network_graph_2, Failure_EBCQ, "Failure_EBCQ")
    
    # Calculating and rescaling edge width
    N1 = list(dict.values(Failure_EBCQ))
    _int = 2
    N1 = [x for x in N1]
    N1 = [0.5 if x<0.5 else x for x in N1]
    
    # Weights colors
    for u,v,d in network_graph_2.edges(data=True):
        d['Failure_EBCQ'] 
    
    edges, weights = zip(*nx.get_edge_attributes(network_graph_2,'Failure_EBCQ').items())
    cmap = mpl.colormaps['jet']
    
    # Plotting new graph 
    Failure_EBCQ.update((key, round(val, 3)) for key, val in Failure_EBCQ.items())
    edge_labels = Failure_EBCQ

    #nodes = nx.draw_networkx_nodes(network_graph_2, pos=pos,node_size= 1.0, node_color='black')
    #edges = nx.draw_networkx_edges(network_graph_2, pos=pos,width=list(N1), edge_color=weights, edge_cmap= cmap)
    #edges_Label=nx.draw_networkx_edge_labels(network_graph_2, pos, edge_labels= edge_labels) 
    
    #ax = plt.gca()
    #ax.set_title('Failure EBCQ')
    
    #plt.colorbar(edges, shrink=0.5, pad=0)
    #plt.show()
    
    # Getting the 5 most critical pipes
    M_failure_names = dict((name[key], value) for (key, value) in M_failure.items())
    #critical_pipes_sorted = sorted(M_failure_names, key=M_failure_names.get, reverse = False)
    #print('The 5 most critcal pipes are:', critical_pipes_sorted[:5])

    #print(M_failure_names)

    # rewrite values to int()
    M_failure_int = {}
    for key, val in M_failure_names.items():
        M_failure_int[key] = int(val)

    demand_impacted_graph_path = output_dir + '/demand_impacted_graph.json'
    with open(demand_impacted_graph_path, 'w') as f:
        f.write(json.dumps(M_failure_int))
    
    #demand_impacted_output = pd.DataFrame.from_dict(Failure_EBCQ, orient="index")
    #demand_impacted_output.to_csv(demand_impacted_graph_path, sep=';')
    
    print('Duration: {}'.format(time.time()-start_time))

    return True

