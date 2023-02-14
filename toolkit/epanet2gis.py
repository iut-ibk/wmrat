import sys
import json
import epanet_util as enu
import os

if len(sys.argv) != 4:
    print(f'usage: {sys.argv[0]} <source-epsg> <epanet-inp> <target-dir>', file=sys.stderr)
    sys.exit(1)

source_epsg = int(sys.argv[1])
epanet_path = sys.argv[2]
target_dir = sys.argv[3]

success, val = enu.epanet_inp_read(epanet_path)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

epanet_dict = val

success, val = enu.epanet_to_graph(epanet_dict)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

nodes, edges = val

success, val = enu.graph_to_geojsons(nodes, edges, source_epsg)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

nodes_geojson, edges_geojson = val

with open(target_dir + '/nodes.geojson', 'w') as f:
    json.dump(nodes_geojson, f)

with open(target_dir + '/edges.geojson', 'w') as f:
    json.dump(edges_geojson, f)

