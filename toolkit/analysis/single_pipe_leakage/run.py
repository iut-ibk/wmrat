# leak analysis
import wntr
import os
import re
import pandas as pd
import sys
import math
import networkx as nx

import graph_editing
import misc_light
import openpyxl

import numpy as np
from matplotlib.colors import Normalize

def run(epanet_inp_path, param_dict, output_dir):
    area_dict = {
        'c': [10, 10, 25, None, 25, None, None],
        'l': [40, 40, 40, None, 40, None, None],
        'r': [None, None, None, 15, 15, 15, 50],
        'j': [None, None, 15, 15, 15, 5, 5]
    }
    
    exponent_data = {
        'c': [0.5, 0.5, 0.5, None, 0.5, None, None],
        'l': [15, 1.5, 0.9, None, 0.85, None, None],
        'r': [None, None, None, 1.5, 1.5, 1.5, 1.5],
        'j': [None, None, 1, 1, 1, 1, 1]
    }
    
    #list_material = ['PE', 'PVC', 'Asbestos-cement', 'Concrete', 'GUSS', 'GGGUSS', 'STZ']

    material_info_str = dict({k: {'area': area, 'exponent': exponent} for [k, area, exponent] in param_dict['material_info']})
    material_info = {}

    for k, v in material_info_str.items():
        area_str = v['area']
        exp_str = v['exponent']
        entry = {
            'area': float(area_str) if area_str else None,
            'exponent': float(exp_str) if exp_str else None,
        }
        material_info[k] = entry

    list_tanks = dict({k: v for k, v in param_dict['outflow_map']})
    #print(list_tanks)

    #list_tanks = {'6154': 'HB_Kraken', '6163': 'HB_Pertrach', '1730': 'HB_Pirchanger', '6139': 'HB_Schmadl'}

    list_tanks_l = list_tanks.values()
    
    negative_outflow_kraken = {}
    
    #counter
    u = 0
    
    # discharge coeffiecient constant value
    discharge_coefficient = 0.6
    
    negative_outflow_kraken = {}
    
    ##wntr input
    inp_file = epanet_inp_path
    wn = wntr.network.WaterNetworkModel(inp_file)
    
    wn.options.hydraulic.demand_model = 'PDD'
    
    wn.options.time.duration = 0
    
    wn.options.time.hydraulic_timestep: int = 1
    wn.options.time.report_timestep: int = 1
    
    sim = wntr.sim.EpanetSimulator(wn)
    results = sim.run_sim(file_prefix='pipeburst_normal_tmp')
    flow_normal = results.link['flowrate']
    
    #define the list of outflow pipes
    list_outflow = list_tanks.keys()
    flow_rates_outflow_normal = {}
    for pipe_id_list in list_outflow:
            flow_rates_outflow_normal[pipe_id_list] = flow_normal.loc[:,pipe_id_list][0]
    
    #### volume of tank calculatin
    def calculate_volume_per_meter(radius, height):
        volume = math.pi * radius**2 * height
        
        return volume
    
    tank_dimensions = {}
    for i in list_tanks_l:
        tank = wn.get_node(i)
        tank_radius = tank.diameter / 2
        tank_height = tank.max_level 
        volume = calculate_volume_per_meter(tank_radius, tank_height)
        tank_dimensions[i] = volume * 1000
    
    # Find the node object for 'HB_Kraken
    flow_results = {}
    
    pipe_ids = wn.pipe_name_list
    
    ### getting the pipe data from wntr
    matching_pipe_tag = {}
    for pipe_id in pipe_ids:
        pipe = wn.get_link(pipe_id)    
        matching_pipe = pipe
    
        if matching_pipe.tag == None:
            continue
    
        else:
            matching_pipe_tag_1 = matching_pipe.tag
            matching_pipe_tag = re.sub(r'\d+', '', matching_pipe_tag_1)
    
        area =  {}
        exponent = {}
    
        # Matching with the table data
        if matching_pipe_tag in material_info.keys():
            area = material_info[matching_pipe_tag]['area']
            exponent = material_info[matching_pipe_tag]['exponent']
        else:
            area = material_info['default']['area']
            exponent = material_info['default']['exponent']
    
        # Assigning the values to EPANET
        if exponent == None and area == None:
            continue
    
        else:
            wn = wntr.morph.split_pipe(wn, pipe_id, f'leak_pipe_strat_{pipe_id}', f'leak_pipe_end_{pipe_id}')
            leak_node = wn.get_node(f'leak_pipe_end_{pipe_id}')
    
            wn.options.hydraulic.emitter_exponent = exponent
            leakage_c = discharge_coefficient * area * math.sqrt(2 * 9.81)
            leak_node.emitter_coefficient = leakage_c
    
            # WNTR simulation
            wn.options.hydraulic.demand_model = 'PDD'
            wn.options.time.duration = 0
            wn.options.time.hydraulic_timestep: int = 1
            wn.options.time.report_timestep: int = 1
            sim_L = wntr.sim.EpanetSimulator(wn)
            results_L = sim_L.run_sim(file_prefix='pipeburst_alt_tmp')
                
            # leak analsyis
            flow_leak = results_L.link['flowrate']
    
            flow_rates_outflow_leak = {}
            for pipe_id_list in list_outflow:
                    flow_rates_outflow_leak[pipe_id_list] = flow_leak.loc[:,pipe_id_list][0]
            
            for key, values in flow_rates_outflow_leak.items():
                    diff_flow = (abs(values - flow_rates_outflow_normal[key])) * 1000
                    tank = list_tanks[key]
    
                    if diff_flow < 0.1:
                         continue
                    
                    else:
                         leak_1min = diff_flow * 60
                         m310_leak = (10000 / diff_flow)
    
                         if (m310_leak > tank_dimensions[tank]):
                              m310_leak = (tank_dimensions[tank]/diff_flow)
                              negative_outflow_kraken[u] = [pipe_id, tank_dimensions[tank] / 1000, tank_dimensions[tank], diff_flow, leak_1min, m310_leak, 'tank empty']
                              u = u +1
    
                         else:
                              negative_outflow_kraken[u] = [pipe_id, tank_dimensions[tank] / 1000, tank_dimensions[tank], diff_flow, leak_1min, m310_leak, '10 cubic meters empty']
                              u = u +1
    
        wn = wntr.network.WaterNetworkModel(inp_file)
        
    # Convert the dictionary to a DataFrame
    df = pd.DataFrame(negative_outflow_kraken)
    
    # Provide the path where you want to save the Excel file
    file_path = output_dir + '/output_data.xlsx'
    
    # Save the DataFrame to Excel
    df.to_excel(file_path, index=False)
    
    #####################transpose
    def transpose_excel_sheet(input_filename, output_filename):
        # Read the Excel file
        df = pd.read_excel(input_filename)
    
        # Transpose the data
        df_transposed = df.transpose()
    
        # Save the transposed data to a new Excel file
        df_transposed.to_excel(output_filename, index=False)
    
    # Replace 'input_data.xlsx' with the actual Excel file name you want to transpose
    # Replace 'output_data.xlsx' with the desired name for the transposed Excel file
    output_filename = output_dir + '/input_data.xlsx'
    input_filename = output_dir + '/output_data.xlsx'
    transpose_excel_sheet(input_filename, output_filename)

    csvs_dir = output_dir + '/csvs'
    os.makedirs(csvs_dir, exist_ok=True)
    
    ########sorting according to tanks
    def sort_and_save_by_similarity(input_filename):
        # Read the Excel file
        df = pd.read_excel(input_filename)
    
        # Determine the column index that contains the content for sorting
        # Replace '2' with the actual column number (indexing starts from 0) containing the content for sorting
        column_index = 1
    
        # Sort the DataFrame based on the specified column
        sorted_df = df.sort_values(by=column_index)
    
        # Determine unique values in the specified column for grouping
        unique_values = sorted_df.iloc[:, column_index].unique()
    
        # Create a Pandas Excel writer
        writer = pd.ExcelWriter(output_dir + '/output_sorted_by_similarity.xlsx', engine='xlsxwriter')
    
        # Write each group to a separate sheet
        for value in unique_values:
            sheet_name = f'Similarity_{value}'
            df_group = sorted_df[sorted_df.iloc[:, column_index] == value]
            df_group.drop(column_index, axis=1, inplace=True)  # Remove the specified column from the sorted groups
            csv_name = csvs_dir + f'/{value}.csv'
            df_group.to_csv(csv_name, index=False)
            df_group.to_excel(writer, sheet_name=sheet_name, index=False)
    
        # Save the Excel file
        writer.close()
    
    # Call the function with the input Excel file name
    input_filename = output_dir + '/input_data.xlsx'
    sort_and_save_by_similarity(input_filename)
    
    inp_file = epanet_inp_path
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
    max_demand = max(demands.values())
    
    # Read data from the Excel file
    excel_file = output_dir + '/output_sorted_by_similarity.xlsx'
    wb = openpyxl.load_workbook(excel_file)
    sheet = wb.active
    
    # Extract data from the Excel file
    excel_data = {}
    for row in sheet.iter_rows(values_only=True):
        name_value = row[0]
        category_value = row[1]
        excel_data[name_value] = category_value
    
    # Create a new graph with matching edges and nodes
    new_graph = nx.Graph()
    for edge in network_graph.edges(data=True):
        edge_data = edge[2]  # Get the dictionary of edge attributes
        if name[edge[:2]] in excel_data:
            edge_data['category'] = excel_data[name[edge[:2]]]  # Add the third column value as an attribute
            new_graph.add_edge(*edge[:2], **edge_data)
    for node, data in network_graph.nodes(data=True):
        new_graph.add_node(node, **data)
    
    # Extract the 'category' values from the new graph
    category_values = [data.get('category', 0) for _, _, data in new_graph.edges(data=True)]
    
    # Divide the 'category' values into different bins or ranges
    num_bins = 10  # Adjust this value to control the number of different ranges
    _, bin_edges = np.histogram(category_values, bins=num_bins)
    bin_edges = np.unique(bin_edges)  # Make sure we have unique bin edges
    
    # Plot the original graph in black
    #plt.figure(figsize=(10, 6))
    #pos = nx.get_node_attributes(network_graph, 'pos')
    
    #nx.draw(network_graph, pos, node_color='black', node_size = 0.001, edge_color='lightgrey', width=1, with_labels=False, font_weight='bold')
    
    # Plot the new graph with color-coded edges based on different ranges and reduced node size
    #pos_new = nx.get_node_attributes(new_graph, 'pos')
    #node_size = 0.1  # Set the node size to a smaller value
    #norm = Normalize(vmin=min(bin_edges), vmax=max(bin_edges))
    #for edge in new_graph.edges(data=True):
    #    source, target, data = edge
    #    category = data.get('category', 0)
    #    color = plt.cm.rainbow(norm(category)) # Map the 'category' value to a color based on the colormap
    #    nx.draw_networkx_edges(new_graph, pos_new, edgelist=[(source, target)], edge_color=color, width=4)
    
    # Draw the nodes with reduced size
    #nx.draw_networkx_nodes(new_graph, pos_new, node_color='black', node_size=node_size)
    
    # Add color bar
    #sm = plt.cm.ScalarMappable(cmap=plt.cm.rainbow, norm=norm)  # Use 'rainbow' colormap for the color bar
    #sm.set_array([])
    #cbar = plt.colorbar(sm, label='Category from Excel Column 3')
    
    #plt.title('Network Graph with Color-Coded Edges')
    #plt.show()
    
    return None, False
