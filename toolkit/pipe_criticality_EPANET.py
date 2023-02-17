import wntr
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import rankdata
import pandas as pd
import time

start_time = time.time()

# Create a water network model

inp_file = 'C:/Users/c8451349/Desktop/No_Valves/EPANET_Final/Simplified Models/Skeletal Model/No_Valves_No_Hydrants_WaterGEMS/WaterGEMS/Merge_Different_Pipe_diameters/No_valves_iteration_7_681_pipes_smart_pipe_removal_a.inp'
wn = wntr.network.WaterNetworkModel(inp_file)


# Simulation Options for criticality analysis

analysis_end_time = 72*3600
wn.options.time.duration = analysis_end_time
wn.options.hydraulic.demand_model = "DD"
wn.options.hydraulic.required_pressure = 35.00
wn.options.hydraulic.minimum_pressure = 0


# Create a list of pipes with defined diameter to include in the analysis

pipes = wn.query_link_attribute("diameter", np.greater_equal, 0.001, link_type=wntr.network.model.Pipe)
pipes = list(pipes.index)
wntr.graphics.plot_network(wn, link_attribute=pipes, title='Pipes included in criticality analysis')
plt.show()


# Define pressure threshold

pressure_threshold = 11                         # usually same as pt_abnormal
pressure_threshold_abnormal = 11                # usually same as pt_normal, but always pt_normal > pt_abnormal

# Run a preliminary simulation to determine if junctions drop below threshold during normal condition

sim = wntr.sim.EpanetSimulator(wn)
results = sim.run_sim()


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
    results = sim.run_sim()

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
int = 7
N1 = [x / int for x in N1]
N1 = [0.5 if x==0 else x for x in N1]

wntr.graphics.plot_network(wn, link_attribute=demand_impacted, node_size=0, link_width=N1, title="Not delivered demand\nfor each pipe closure")
plt.show()

#pipe_name = "P-1"

#wntr.graphics.plot_network(wn, node_attribute=list(junctions_impacted[pipe_name]), link_attribute=[pipe_name], node_size=20, title='Pipe ' + pipe_name + ' is critical \nfor pressure conditions at '+str(number_of_junctions_impacted[pipe_name])+' nodes')
#plt.show()


# Create pipe ranking and getting the 5 most critical pipes 

M_failure = dict(zip(demand_impacted.keys(), rankdata([-i for i in demand_impacted.values()], method='min')))
Most_critical_pipes = sorted(M_failure, key=M_failure.get, reverse = False)[:5]
print('The Most Critcal Pipes are:', Most_critical_pipes)

demand_impacted_output = pd.DataFrame.from_dict(demand_impacted, orient="index")
demand_impacted_output.to_csv("demand_impacted.csv", sep=';')


print('Duration: {}'.format(time.time()-start_time))

a = 0