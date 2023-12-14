import itertools as it
import random
import datetime as dt
import string
from shapely.geometry import Point, Polygon
import networkx as nx
import alphashape
import geojson
import collections as c
import subprocess as sp
from pyproj import Transformer

def run_epanet_and_collect_results(epanet_bin_path, epanet_inp_path, epanet_rep_path):
    p = sp.Popen([epanet_bin_path, epanet_inp_path, epanet_rep_path], stdout=sp.PIPE, stderr=sp.PIPE)
    out, err = p.communicate()

    if p.returncode != 0:
        return False, f'fatal: running EPANET failed: stdout:\n{out}\nstderr:\n{err}'

    success, val = epanet_rep_read(epanet_rep_path)
    if not success:
        return False, f'fatal: parsing EPANET report failed: {val}'

    epanet_rep_dict = val
    return True, epanet_rep_dict

def epanet_rep_read(path):
    lines = []

    #NOTE: support nodes with demand, head and pressure and links with flow, velocity and headloss
    report_dict = {
        'nodes': {},
        'links': {},
        'summary': {}
    }

    node_result_offsets = []
    link_result_offsets = []

    try:
        # first pass: parse summary and result offsets
        with open(path) as f:
            for line_nr, line in enumerate(f):
                # record node and link result offsets
                if 'Node Results at' in line:
                    node_result_offsets += [line_nr]
                if 'Link Results at' in line:
                    link_result_offsets += [line_nr]

                # from summary (nodes):
                if 'Number of Junctions' in line:
                    n_junctions = int(line.split()[-1])
                if 'Number of Reservoirs' in line:
                    n_reservoirs = int(line.split()[-1])
                if 'Number of Tanks' in line:
                    n_tanks = int(line.split()[-1])

                # from summary (links):
                if 'Number of Pipes' in line:
                    n_pipes = int(line.split()[-1])
                if 'Number of Pumps' in line:
                    n_pumps = int(line.split()[-1])
                if 'Number of Valves' in line:
                    n_valves = int(line.split()[-1])

                lines.append(line)

        report_dict['summary']['n_junctions'] = n_junctions
        report_dict['summary']['n_reservoirs'] = n_reservoirs
        report_dict['summary']['n_tanks'] = n_tanks

        report_dict['summary']['n_pipes'] = n_pipes
        report_dict['summary']['n_pumps'] = n_pumps
        report_dict['summary']['n_valves'] = n_valves

        n_nodes = n_junctions + n_reservoirs + n_tanks
        n_links = n_pipes + n_pumps + n_valves

        # second pass: parse actual results (nodes):
        for node_result_offset in node_result_offsets:
            start_line = node_result_offset + 5

            for line_nr in range(start_line, start_line + n_nodes):
                parts = lines[line_nr].split()

                name = parts[0]
                demand = float(parts[1])
                head = float(parts[2])
                pressure = float(parts[3])

                # initialize node dictionary on first timestep
                if name not in report_dict['nodes']:
                    report_dict['nodes'][name] = {
                        'demand': [],
                        'head': [],
                        'pressure': [],
                    }

                report_dict['nodes'][name]['demand'] += [demand]
                report_dict['nodes'][name]['head'] += [head]
                report_dict['nodes'][name]['pressure'] += [pressure]

        # second pass: parse actual results (links):
        for link_result_offset in link_result_offsets:
            start_line = link_result_offset + 5

            for line_nr in range(start_line, start_line + n_links):
                parts = lines[line_nr].split()

                name = parts[0]
                flow = float(parts[1])
                velocity = float(parts[2])
                headloss = float(parts[3])

                # initialize link dictionary on first timestep
                if name not in report_dict['links']:
                    report_dict['links'][name] = {
                        'flow': [],
                        'velocity': [],
                        'headloss': [],
                    }

                report_dict['links'][name]['flow'] += [flow]
                report_dict['links'][name]['velocity'] += [velocity]
                report_dict['links'][name]['headloss'] += [headloss]

    except Exception as e:
        return False, str(e)

    return True, report_dict

def epanet_inp_read(path):
    # read lines
    lines = []
    try:
        with open(path) as f:
            for line in f:
                lines.append(line)
    except Exception as e:
        return False, str(e)

    # preprocess
    lines_pp = list(epanet_inp_preprocess(lines))
    nlines = len(lines_pp)

    i = 0
    expect_header = True

    # parse into dictionary
    inp = c.OrderedDict() #NOTE: do not mess with section order!
    while i < nlines:
        l = lines_pp[i]
        if expect_header:
            if l[0] == '[' and l[-1] == ']':
                name = l[1:-1]
                data = []
                expect_header = False
            else:
                return False, 'internal error: expected \'[\', found: \'' + l + '\''
        else:
            if l[0] == '[':
                inp[name] = data
                expect_header = True
                i -= 1
            else:
                data.append(l.split())
        i += 1

    # remainder
    if data:
        inp[name] = data

    return True, inp

def epanet_inp_preprocess(lines):
    lines = map(lambda l : ''.join(it.takewhile(lambda c : c not in ";\n\r", l)), lines) # get rid of comments ...
    lines = filter(lambda l : any(map(lambda c : c in string.printable, l)), lines)      # ... and blank lines
    return lines

def epanet_inp_write(inp, path): 
    with open(path, 'w') as f:
        for name, lines in inp.items():
            f.write('[' + name + ']\n')
            for l in lines:
                f.write(' '.join(l) + '\n')
            f.write('\n')

# rewrite an EPANET dictionary to a graph (edges, nodes) with corresponding parameters
# depending on the component:
#
# nodes: junctions, reservoirs and tanks
# edges: pipes, pumps and valves
#
def epanet_to_graph(epanet_dict): 
    nodes = {}
    edges = {}

    if 'VERTICES' not in epanet_dict.keys():
        return False, 'EPANET input file does not contain a [VERTICES] section'

    if 'COORDINATES' not in epanet_dict.keys():
        return False, 'EPANET input file does not contain a [COORDINATES] section'

    try:
    
        # nodes: junctions
        for junction_params in epanet_dict['JUNCTIONS']:
            name = junction_params[0]
    
            elevation = float(junction_params[1])
    
            nodes[name] = {
                'type': 'JUNCTION',
                'coords': [],
                'param': {
                    'elevation': elevation
                },
            }
    
            if len(junction_params) > 2:
                demand = float(junction_params[2])
                nodes[name]['param']['demand'] = demand
    
            if len(junction_params) > 3:
                pattern = junction_params[3]
                nodes[name]['param']['pattern'] = pattern
    
        # nodes: reservoirs
        for reservoir_param in epanet_dict['RESERVOIRS']:
            name = reservoir_param[0]
    
            head = float(reservoir_param[1])
    
            nodes[name] = {
                'type': 'RESERVOIR',
                'coords': [],
                'param': {
                    'head': head,
                },
            }
    
            if len(reservoir_param) > 2:
                pattern = reservoir_param[2]
                nodes[name]['param']['pattern'] = pattern
    
        # nodes: tanks
        for tank_params in epanet_dict['TANKS']:
            name = tank_params[0]
    
            elevation = float(tank_params[1])
            init_level = float(tank_params[2])
            min_level = float(tank_params[3])
            max_level = float(tank_params[4])
            diameter = float(tank_params[5])
            min_vol = float(tank_params[6])
    
            nodes[name] = {
                'type': 'TANK',
                'coords': [],
                'param': {
                    'elevation': elevation,
                    'init_level': init_level,
                    'min_level': min_level,
                    'max_level': max_level,
                    'diameter': diameter,
                    'min_vol': min_vol,
                },
            }
    
            if len(tank_params) > 7:
                vol_curve = tank_params[7]
                nodes[name]['param']['vol_curve'] = vol_curve

        #NOTE: emitters are currently not supported
    
        # edges: pipes
        for pipe_params in epanet_dict['PIPES']:
            name, node1, node2 = pipe_params[:3]
    
            length = float(pipe_params[3])
            diameter = float(pipe_params[4])
            roughness = float(pipe_params[5])

            edges[name] = {
                'type': 'PIPE',
                'coords': [],
                'node1': node1,
                'node2': node2,
                'param': {
                    'length': length,
                    'diameter': diameter,
                    'roughness': roughness,
                }
            }
    
            if len(pipe_params) == 8:
                edges[name]['param']['mloss'] = float(pipe_params[6])
                edges[name]['param']['status'] = pipe_params[7] # OPEN, CLOSED or CV
    
        # edges: pumps
        if 'PUMPS' in epanet_dict:
            for pump_params in epanet_dict['PUMPS']:
                name, node1, node2 = pump_params[:3]
    
                edges[name] = {
                    'type': 'PUMP',
                    'coords': [],
                    'node1': node1,
                    'node2': node2,
                    'param': {},
                }
    
                for i in range(3, len(pump_params), 2):
                    key = pump_params[i]
                    val = pump_params[i + 1]
    
                    edges[name]['param'][key] = val
    
        # edges: valves
        if 'VALVES' in epanet_dict:
            for valve_params in epanet_dict['VALVES']:
                name, node1, node2 = valve_params[:3]
    
                diameter = float(valve_params[3])
                valve_type = valve_params[4]
                valve_setting = valve_params[5]
                minor_loss = float(valve_params[6])
    
                edges[name] = {
                    'type': 'VALVE',
                    'coords': [],
                    'node1': node1,
                    'node2': node2,
                    'param': {
                        'diameter': diameter,
                        'type': valve_type,
                        'setting': valve_setting,
                        'minor_loss': minor_loss,
                    },
                }
    
        #NOTE: useful for debugging
        #print('nodes')
        #for key, val in nodes.items():
        #    print(key)
        #    print(val)
    
        #print('edges')
        #for key, val in edges.items():
        #    print(key)
        #    print(val)
    
        # coordinates of nodes
        for coord_params in epanet_dict['COORDINATES']:
            key, c0, c1 = coord_params[:3]
    
            nodes[key]['coords'].append([float(c0), float(c1)])
    
        # *interior* vertices of edges
        for coord_params in epanet_dict['VERTICES']:
            key, c0, c1 = coord_params[:3]
    
            edges[key]['coords'].append([float(c0), float(c1)])
    
        # add the 2 missing *exterior* coordinates to edge coordinates
        for edge_params in edges.values():
            node1_coords = nodes[edge_params['node1']]['coords']
            node2_coords = nodes[edge_params['node2']]['coords']
    
            interior_coords = edge_params['coords']
            edge_params['coords'] = node1_coords + interior_coords + node2_coords

        return True, (nodes, edges)

    except Exception as e:
        return False, f'unable to transform EPANET dictionary to graph: {e}'

#NOTE: coordinate system is EPSG 4326 implicitly
def graph_to_geojsons(epanet_nodes, epanet_edges, epanet_epsg_int):
    trans = Transformer.from_crs(f'EPSG:{epanet_epsg_int}', 'EPSG:4326')

    # nodes (GeoJSON)
    geojson_nodes = {
        'type': 'FeatureCollection',
        'name': 'nodes',
        'features': [],
    }

    features = []
    for node, node_params in epanet_nodes.items():
        trans_coords = []

        for c0, c1 in node_params['coords']:
            #NOTE: coords are reversed in coord sections [?]
            trans_c1, trans_c0 = trans.transform(c1, c0)
            trans_coords.append([trans_c0, trans_c1])

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': trans_coords[0],
            },
            'properties': {
                'id': node,
                'type': node_params['type'],
                'param': node_params['param'],
            }
        }

        features.append(feature)

    geojson_nodes['features'] = features

    # edges (GeoJSON)
    geojson_edges = {
        'type': 'FeatureCollection',
        'name': 'edges',
        'features': [],
    }

    features = []
    for edge, edge_params in epanet_edges.items():
        trans_coords = []

        if len(edge_params['coords']) == 0:
            print('warning: {edge} does not have coordinates, skipping ...', file=sys.stderr)
            continue

        for c0, c1 in edge_params['coords']:
            #NOTE: coords are reversed in coord sections [?]
            trans_c1, trans_c0 = trans.transform(c1, c0)
            trans_coords.append([trans_c0, trans_c1])

        feature = {
            'type': 'Feature',
            'geometry': {
                'type': 'LineString',
                'coordinates': trans_coords,
            },
            'properties': {
                'id': edge,
                'type': edge_params['type'],
                'param': edge_params['param'],
            }
        }

        features.append(feature)

    geojson_edges['features'] = features

    return True, (geojson_nodes, geojson_edges)

def epanet_segments_via_valves(nodes, edges):
    G = nx.Graph()
    for node, node_info in nodes.items():
        G.add_node(node, x=node_info['coords'][0][0], y=node_info['coords'][0][1])

    valves = dict()
    for edge_name, edge_info in edges.items():
        if edge_info['type'] == 'VALVE':
            valves[edge_name] = edge_info
        else:
            node1 = edge_info["node1"]
            node2 = edge_info["node2"]
            G.add_edge(node1, node2, name=edge_name)

    then = dt.datetime.now()
    connected_components = list(nx.connected_components(G))

    segment_valves_map = {}
    for i, segment in enumerate(connected_components):
        segment_valves_map[i] = {
            'nodes': segment,
            'valves': set(),
            'edges': set(),
        }

        for edge_name, edge_info in edges.items():
            if edge_info['node1'] in segment or edge_info['node2'] in segment:
                segment_valves_map[i]['edges'].add(edge_name)

        for valve, valve_info in valves.items():
            if valve_info['node1'] in segment or valve_info['node2'] in segment:
                segment_valves_map[i]['valves'].add(valve)

    elapsed_time_s = (dt.datetime.now() - then).total_seconds()
    print('finding components took', elapsed_time_s)

    return segment_valves_map

def segments_to_geojson(segment_valves_map, edges_with_attributes, source_epsg):
    trans = Transformer.from_crs(f'EPSG:{source_epsg}', 'EPSG:4326')

    edge_features = []
    valve_features = []
    for segment_id, segment_info in segment_valves_map.items():
        edges = segment_info['edges']
        valves = segment_info['valves']

        # pipes
        multi_edges = []
        for edge in edges:
            edge_info = edges_with_attributes[edge]

            edge_coords = []
            for c0, c1 in edge_info['coords']:
                trans_c1, trans_c0 = trans.transform(c1, c0)
                edge_coords.append([trans_c0, trans_c1])

            multi_edges.append(edge_coords)

        feature = geojson.Feature(
            geometry=geojson.MultiLineString(multi_edges),
            properties={'segment_id': segment_id}
        )
        edge_features.append(feature)

        # valves
        multi_valves = []
        for valve in valves:
            valve_info = edges_with_attributes[valve]

            valve_coords = []
            for c0, c1 in valve_info['coords']:
                trans_c1, trans_c0 = trans.transform(c1, c0)
                valve_coords.append([trans_c0, trans_c1])

            multi_valves.append(valve_coords)

        feature = geojson.Feature(
            geometry=geojson.MultiLineString(multi_valves),
            properties={'segment_id': segment_id}
        )
        valve_features.append(feature)

    edge_feature_collection = geojson.FeatureCollection(edge_features)
    valve_feature_collection = geojson.FeatureCollection(valve_features)

    return True, (edge_feature_collection, valve_feature_collection)

