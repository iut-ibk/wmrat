import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime as dt
import json
import pandas as pd

def create_graph(val, link_attribute):
    G = nx.MultiDiGraph()

    node_sizes = []
    node_colors = []
    link_color = []

    # network nodes
    for node in val['JUNCTIONS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])))
                # flood_volume = flooding_nodes.get(name)
                # if flood_volume > 0:
                #     node_size = 15
                # else:
                #     node_size = 3    
                # node_sizes.append(node_size)
                # node_color = flood_volume/flooding_node_max*2
                # node_colors.append(node_color)

                
                #nx.set_node_attributes(G, name='pos', values={name: (line[0][1], line[0][2])})
                #nx.set_node_attributes(G, name='type', values={name: 'JUNCTIONS'})

    for node in val['RESERVOIRS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])))  
                # flood_volume = flooding_nodes.get(name)
                # if flood_volume > 0:
                #     node_size = 15
                # else:
                #     node_size = 3  
                # node_color = flood_volume/flooding_node_max
                # node_colors.append(node_color)

    for node in val['TANKS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])))
                # flood_volume = flooding_nodes.get(name)
                # if flood_volume > 0:
                #     node_size = 15
                # else:
                #     node_size = 3  
                # node_color = flood_volume/flooding_node_max
                # node_colors.append(node_color)

    # network links
    for link in val['PIPES']:
                name = link[0]
                start_node = link[1]
                end_node = link[2]
                if name in link_attribute:
                    link_color = 'r'
                else:
                    link_color = 'k'
                G.add_edge(start_node, end_node, color = link_color, key=name)


    for link in val['PUMPS']:
                name = link[0]
                start_node = link[1]
                end_node = link[2]
                if name in link_attribute:
                    link_color = 'r'
                else:
                    link_color = 'k'
                G.add_edge(start_node, end_node, color = link_color, key=name)

    for link in val['VALVES']:
                name = link[0]
                start_node = link[1]
                end_node = link[2]
                if name in link_attribute:
                    link_color = 'r'
                else:
                    link_color = 'k'
                G.add_edge(start_node, end_node, color = link_color, key=name)

    G = G.to_undirected()
    position = nx.get_node_attributes(G,'pos')
    
    return G, position #, node_sizes, node_colors    

def create_graph_of_epanet_file(val):
  
    G = nx.Graph()
   
    edge_colors = []

    # network nodes
    for node in val['JUNCTIONS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                demands = node [2]
                elevations = node [1]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])), demand= float(demands), elevation = float(elevations))

                
                #nx.set_node_attributes(G, name='pos', values={name: (line[0][1], line[0][2])})
                #nx.set_node_attributes(G, name='type', values={name: 'JUNCTIONS'})

    for node in val['RESERVOIRS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                elevations = node [1]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])), elevation = float(elevations))  

    for node in val['TANKS']:
                name = node[0]
                line = [s for s in val['COORDINATES'] if name == s[0]]
                elevations = node [1]
                G.add_node(name, pos=(float(line[0][1]), float(line[0][2])), elevation = float(elevations))


    # network links
    for link in val['PIPES']:
                name = link[0]
                start_node = link[1]
                end_node = link[2]
                length = float(link[3])
                diameter= float(link [4])
                weight= (length*1000)/diameter
    
                
                #edge_color = weight
                #edge_colors.append(edge_color)

                G.add_edge(start_node, end_node, len=length, dia=diameter, Wei=weight, key=name)


    for link in val['PUMPS']:
               name = link[0]
               start_node = link[1]
               end_node = link[2]
               G.add_edge(start_node, end_node, len=0.5, key=name)

    
    for link in val['VALVES']:
                 name = link[0]
                 start_node = link[1]
                 end_node = link[2]
                 diameter = float(link[3])
                 weight = (0.5*1000)/diameter
                 G.add_edge(start_node, end_node, len=0.5, dia = diameter, Wei = weight, key=name)

    #G = G.to_undirected()
   
    return G

def distance_nodes(graph, csv_name):
    shortest_path_length = dict(nx.all_pairs_dijkstra_path_length(graph, weight='len'))
    distance_nodes = pd.DataFrame.from_dict(shortest_path_length, orient='index')
    distance_nodes.to_csv(csv_name, sep=';')