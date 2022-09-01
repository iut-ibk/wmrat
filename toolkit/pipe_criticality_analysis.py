# this is taken and adapted from the WNTR example dir
import numpy as np
import wntr
import os

def run(wntr_network_obj, param_dict, output_dir):
    wn = wntr_network_obj

    # Adjust simulation options for criticality analyses
    # TODO: @uli: probably do the type stuff somewhere else? ... or maybe not? ... for now it is ok

    analysis_end_time = int(param_dict['analysis_end_time'])
    wn.options.time.duration = analysis_end_time
    wn.options.hydraulic.demand_model = param_dict['demand_model']
    wn.options.hydraulic.required_pressure = float(param_dict['required_pressure'])
    wn.options.hydraulic.minimum_pressure = float(param_dict['min_pressure'])
    
    # Create a list of pipes with large diameter to include in the analysis
    pipes = wn.query_link_attribute('diameter', np.greater_equal, float(param_dict['min_diameter']), link_type=wntr.network.model.Pipe)      
    pipes = list(pipes.index)
       
    # Define the pressure threshold
    pressure_threshold = float(param_dict['pressure_threshold'])
    
    # Run a preliminary simulation to determine if junctions drop below the 
    # pressure threshold during normal conditions
    sim = wntr.sim.WNTRSimulator(wn)
    results = sim.run_sim()
    min_pressure = results.node['pressure'].loc[:,wn.junction_name_list].min()
    below_threshold_normal_conditions = set(min_pressure[min_pressure < pressure_threshold].index)
    
    # Run the criticality analysis, closing one pipe for each simulation
    junctions_impacted = {} 
    for pipe_name in pipes:
    
        # NOTE: could update some progress here ... (but probably not trivial to do it in general?)
        # print('Pipe:', pipe_name)     
        
        # Reset the water network model
        wn.reset_initial_values()
    
        # Add a control to close the pipe
        pipe = wn.get_link(pipe_name)        
        act = wntr.network.controls.ControlAction(pipe, 'status', 
                                                  wntr.network.LinkStatus.Closed)
        cond = wntr.network.controls.SimTimeCondition(wn, '=', '24:00:00')
        ctrl = wntr.network.controls.Control(cond, act)
        wn.add_control('close pipe ' + pipe_name, ctrl)
            
        # Run a PDD simulation
        sim = wntr.sim.WNTRSimulator(wn)
        results = sim.run_sim()
            
        # Extract the number of junctions that dip below the minimum pressure threshold
        min_pressure = results.node['pressure'].loc[:,wn.junction_name_list].min()
        below_threshold = set(min_pressure[min_pressure < pressure_threshold].index)
        
        # Remove the set of junctions that were below the pressure threshold during 
        # normal conditions and store the result
        junctions_impacted[pipe_name] = below_threshold - below_threshold_normal_conditions
            
        # Remove the control
        wn.remove_control('close pipe ' + pipe_name)
    
    # Extract the number of junctions impacted by low pressure conditions for each pipe closure  
    number_of_junctions_impacted = dict([(k,len(v)) for k,v in junctions_impacted.items()])
            
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    filepath = output_dir + '/pipe_criticality_viz.svg'
    wntr.graphics.plot_network(wn, link_attribute=number_of_junctions_impacted, node_size=0, link_width=2, filename=filepath)

