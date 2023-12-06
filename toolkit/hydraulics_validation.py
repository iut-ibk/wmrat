import wntr
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
from scipy.stats import rankdata
import pandas as pd
import time
import copy
from mpl_toolkits.axes_grid1 import make_axes_locatable
import csv
import time

def hydraulics_validation(inp_file, pipes1):
  #start_time = time.time()

  wn = wntr.network.WaterNetworkModel(inp_file)  

  hydraulic_results = {} 
  i = 0
  
  junction_names = wn.junction_name_list  

  # Calculate the total demand
  total_demand = sum(wn.get_node(junction_name).base_demand for junction_name in junction_names)
    
  for key, pipe_name in pipes1.items():
      
    for pipe_name_c in pipe_name:
      wn.get_link(pipe_name_c).initial_status = 'CLOSED'

    # Run the simulation
    wn.options.hydraulic.demand_model = 'PDD'
    wn.options.time.duration = 1
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='hyd_val_tmp')
    
    # Calculate the total demand supplied during the simulation
    demand_supplied_all = results.node['demand'][junction_names].sum(axis=1)
    demand_supplied = demand_supplied_all[0]
    Diff = (total_demand-demand_supplied)*1000

    total = (Diff/total_demand)*100

    # Print the results

    pipe_name_tuple = tuple(pipe_name)
    hydraulic_results[pipe_name_tuple] = Diff
    
    wn.reset_initial_values()
    wn = wntr.network.WaterNetworkModel(inp_file)

    # your code goes here

  #end_time = time.time()
  #runtime = end_time - start_time
  #print("Runtime of the program is:", runtime, "seconds")

  return(hydraulic_results)

