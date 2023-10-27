#####   © Martin Oberascher and Thomas Lindenthaler (2022)  #####

# Related file: Graph_Based_Pipe_Criticality.py

import networkx as nx
import copy
import pickle

# Demand Edge Betweenness Centrality (EBCQ)

def EBCQ(SP, L, K):
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

def EBCQ_dynamic(U, V, network_graph_dynamic, max_demand):
    for node, demand in U.items():
        path_dynamic = nx.shortest_path(network_graph_dynamic, source='1', target = node, weight='Wei')
        if len(path_dynamic) == 1:
            continue
        else:
            for i in range(len(path_dynamic)-1):
                u = path_dynamic[i]
                v = path_dynamic[i+1]
                if(u, v) not in V:
                    V[(v, u)] += float(demand)
                    old_weight = network_graph_dynamic[v][u]['Wei']
                    new_weight = old_weight * (1+(demand/max_demand)**2)
                    network_graph_dynamic[v][u]['Wei']=new_weight
                else:
                    V[(u, v)] += float(demand)
                    old_weight = network_graph_dynamic[u][v]['Wei']
                    new_weight = old_weight * (1+(demand/max_demand)**2)
                    network_graph_dynamic[u][v]['Wei']=new_weight
    return(V)



# Failure EBCQ multiple

def Failure_EBCQ_multiple(EBCQ_normal, EBCQ_normal_R, network_graph, K, Failure_EBCQ_multiple, C_max):
    i = 0
    
    for edges in Failure_EBCQ_multiple:

        if i > 1000:
            break

        if i % 100000 == 0:


            print('Simulated {} combinations of {}'.format(i, len(Failure_EBCQ_multiple)))
            co = str (i) + "Faliure_Multiple.pkl"
            with open(co, "wb") as f:
                    pickle.dump(Failure_EBCQ_multiple, f)

     # Creating a new graph for iteration; Removing 1 edge -> loop
        network_graph_2 = copy.deepcopy(network_graph)

        

        for edge in edges:

            if network_graph_2.has_edge(edge[0], edge[1]):    
                network_graph_2.remove_edge(edge[0], edge[1]) 
            else:
                network_graph_2.remove_edge(edge[1], edge[0])





        failure_weight = 0

        

        
      

        for c in sorted(nx.connected_components(network_graph_2), key=len, reverse=True):
            network_graph_3 = network_graph_2.subgraph(c).copy()
            if 'HB_Kraken' in c:
                L1 = dict()
                L1.update(dict.fromkeys(network_graph_3.edges(), 0.0))
                SP_abnormal = nx.multi_source_dijkstra_path(network_graph_3, sources={'HB_Kraken'}, weight='Wei')
                demands = nx.get_node_attributes(network_graph_3, 'demand')
                EBCQ_abnormal = EBCQ(SP_abnormal, L1, demands)                                                         # same as EBCQ but under abnormal conditions


                # Comparing EBCQ_abnormal with Cmax = Qmax   

                C_delta = { key: EBCQ_abnormal[key] - EBCQ_normal[key] for key in EBCQ_abnormal.keys() if key in EBCQ_normal.keys() and EBCQ_abnormal[key] - EBCQ_normal[key] > 0}
                C_delta.update({key: EBCQ_abnormal[key] - EBCQ_normal_R[key] for key in EBCQ_abnormal.keys() if key not in EBCQ_normal.keys() and EBCQ_abnormal[key] - EBCQ_normal_R[key] > 0})

                #for key in EBCQ_abnormal.items():

                #    if key in EBCQ_normal.keys():

                #        C_delta = {key: EBCQ_abnormal[key] - EBCQ_normal[key] if EBCQ_abnormal[key] - EBCQ_normal[key] > 0}  


                #    else:

                #        C_delta = {key: EBCQ_abnormal[key] - EBCQ_normal_R[key] for key in EBCQ_abnormal if EBCQ_abnormal[key] - EBCQ_normal_R[key] > 0}  


                C_delta_C = {key: C_delta[key] - C_max.get(key, 0) for key in C_delta}               # Comparison delta C_max and EBCQ_delta
                failure_weight += sum(v for v in C_delta_C.values() if v > 0)
            else:

                #reachable_nodes = nx.descendants(network_graph_2, '28') | {'28'}
                reachable_nodes = nx.descendants(network_graph_2, 'HB_Kraken') | {'HB_Kraken'}

                reachable_graph = nx.subgraph(network_graph, reachable_nodes)

                components = list(nx.connected_components(reachable_graph))
                all_nodes = set(network_graph.nodes())
                disconnected_nodes = all_nodes - components[0]

                for node in disconnected_nodes:
                     
                     if node in network_graph_3.nodes:
                        network_graph_3.remove_node(node)

                
                

                for node in disconnected_nodes:


                    
                     # Do something with the disconnected node, such as finding its shortest path to a target node
            
            

                    if node == 'HB_Kraken':

                         continue

                    else:

                        node_data = network_graph_2.nodes[node]['demand']
                        
                        failure_weight = node_data + failure_weight  

                
                L1 = dict()
                L1.update(dict.fromkeys(network_graph_3.edges(), 0.0))

                source_node = 'HB_Kraken'

                # Check if the source node exists in the graph
                if source_node in network_graph_3.nodes():
                    # Extract the connected component containing the source node
                    connected_component = network_graph_3.subgraph(nx.node_connected_component(network_graph_3, source_node))

                    # Find the shortest path from the source node within the connected component
                    SP_abnormal = nx.multi_source_dijkstra_path(connected_component, source_node, weight='Wei')

                else:

                    continue
                    
                    
                             
                demands = nx.get_node_attributes(network_graph_3, 'demand')
                EBCQ_abnormal = EBCQ(SP_abnormal, L1, demands)                                                         # same as EBCQ but under abnormal conditions

                # Comparing EBCQ_abnormal with Cmax = Qmax                                  
                C_delta = {key: EBCQ_abnormal[key] - C_max.get(key, 0) for key in EBCQ_abnormal}               # Comparison delta C_max and EBCQ_delta
                failure_weight += sum(v for v in C_delta.values() if v > 0) 

                

                           
        


        Failure_EBCQ_multiple[edges] = failure_weight
        i += 1





        
        
    return(Failure_EBCQ_multiple)



