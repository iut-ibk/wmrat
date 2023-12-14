import wntr
import numpy as np
import os
import time
import pandas as pd
import matplotlib.pyplot as plt

def run(epanet_inp_path, param_dict, output_dir):
    start_time = time.time()

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    wn=wntr.network.WaterNetworkModel(epanet_inp_path)
    
    analysis_end_time = 24*3600
    wn.options.time.duration = analysis_end_time
    
    junctions = wn.junction_name_list

    pollution_treshold=0
    
    wntr.graphics.plot_network(wn, junctions, node_size=12, link_width=0, title="Junctions included in the analysis")
    plt.show()
    
    sim = wntr.sim.EpanetSimulator(wn)
    results=sim.run_sim()
    sim.run_sim(save_hyd = True)
    wn.options.quality.parameter = 'TRACE'
    
    #min_pollution = results.node['quality'].max(axis=0)
    #above_threshold_normal_conditions = set(min_pollution[min_pollution > pollution_treshold].index)
    
    wn.options.time.hydraulic_timestep = 5*60

    #XXX: run_sim file name ...

    print('#junctions', len(junctions))
    
    junctions_impacted={}
    for inj_node in junctions:
        print(inj_node)
        wn.reset_initial_values()
        wn.options.quality.trace_node = inj_node
        sim_results = sim.run_sim(use_hyd = True)
        trace = sim_results.node['quality']
        trace = trace.stack()
        trace = trace.reset_index()
        trace.columns = ['T', 'Node', inj_node]
    
        sim = wntr.sim.EpanetSimulator(wn)
        results = sim.run_sim()
    
        min_pollution = results.node["quality"].max(axis=0)
        above_threshold = set(min_pollution[min_pollution > pollution_treshold].index)
    
        junctions_impacted[inj_node] = above_threshold #- above_threshold_normal_conditions
    
    number_of_junctions_impacted = dict([(k, len(v)) for k,v in junctions_impacted.items()])
    print("Number of junctions impacted for each node:", number_of_junctions_impacted)
    
    wntr.graphics.plot_network(wn, node_attribute=number_of_junctions_impacted, node_size=12, link_width=0, title="Number of junctions impacted by pollution\nfor each junction pollution entry")
    cvv= plt.savefig("Graph_weights_edges_Schwaz_Kontamination.png", format="PNG")
    plt.show()
