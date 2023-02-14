import itertools as it
import string
import collections as c
from pyproj import Transformer

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

def epanet_inp_write(f, inp): 
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
                'type': edge_params['type'],
                'param': edge_params['param'],
            }
        }

        features.append(feature)

    geojson_edges['features'] = features

    return True, (geojson_nodes, geojson_edges)

