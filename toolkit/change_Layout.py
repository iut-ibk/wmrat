#### calling the opening the files


original_epanet_file = 'C:/Users/c8451349/Desktop/No_Valves/EPANET_Final/Summer/Different _Tank_Zones.inp'
f = open(original_epanet_file)
success, val_o = misc_light.swmm_input_read(f)
network_graph = graph_editing.create_graph_of_epanet_file(val_o)
pos= nx.get_node_attributes(network_graph, 'pos')

######total households ##################################################################### Use only once


total_houses,dct, dct1 = Number_households.Number_households(val_o)

node_list = list(network_graph.nodes())

houses = {}
for i in node_list:
    if i in dct1.keys():
        houses[i] = dct1[i]
    else:
        houses[i] = 0


#######################################################################################################



pos = nx.kamada_kawai_layout(network_graph)
demands = nx.get_node_attributes(network_graph, 'demand')
#total_demand = sum(demands.values())
#weights = nx.get_edge_attributes(network_graph, 'Wei')
name = nx.get_edge_attributes(network_graph, 'key')
#elevation = nx.get_node_attributes(network_graph, 'elevation')

import geopandas as gpd
from shapely.geometry import Point, LineString



# Create a GeoDataFrame for nodes
nodes_data = []
for node, pos1 in pos.items():
    point = Point(pos1)

    if node in demands.keys():

        node_data = {
            'node_id': node,            
            'demand': demands[node],
            'houses': houses[node],
            #'elevation': elevation[node],
            'geometry': point
        }

    else:

        node_data = {
            'node_id': node,            
            'demand': 0,
            'houses': houses[node],
            #'elevation': elevation[node],
            'geometry': point
        }
    nodes_data.append(node_data)

nodes_gdf = gpd.GeoDataFrame(nodes_data, crs='EPSG:4326')

# Create a GeoDataFrame for edges
edges_data = []
for edge in network_graph.edges():
    u, v = edge
    line = LineString([pos[u], pos[v]])
    edge_data = {
        'edge_key': network_graph.edges[u, v]['key'],
        #'weight': network_graph.edges[u, v]['Wei'],
        'geometry': line
    }
    edges_data.append(edge_data)

edges_gdf = gpd.GeoDataFrame(edges_data, crs='EPSG:4326')

# Save the GeoDataFrames to shapefiles
output_nodes_shapefile = 'graph_nodes_K.shp'
output_edges_shapefile = 'graph_edges_K.shp'

nodes_gdf.to_file(output_nodes_shapefile)
edges_gdf.to_file(output_edges_shapefile)

print(f"Nodes shapefile '{output_nodes_shapefile}' saved successfully.")
print(f"Edges shapefile '{output_edges_shapefile}' saved successfully.")


sys.exit()