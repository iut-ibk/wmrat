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

nodes, links = val

success, val = enu.graph_to_geojsons(nodes, links, source_epsg)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

nodes_geojson, links_geojson = val

segment_valves_map = enu.epanet_segments_via_valves(nodes, links)

#alpha = 0
#success, val = enu.segments_to_alphashape_geojson(segment_valves_map, nodes, alpha, source_epsg)
success, val = enu.segments_to_geojson(segment_valves_map, links, source_epsg)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

segments_geojson, valves = val

if not os.path.exists(target_dir):
    os.makedirs(target_dir)

with open(target_dir + '/nodes.geojson', 'w') as f:
    json.dump(nodes_geojson, f)

with open(target_dir + '/links.geojson', 'w') as f:
    json.dump(links_geojson, f)

with open(target_dir + '/segments.geojson', 'w') as f:
    json.dump(segments_geojson, f)

with open(target_dir + '/valves.geojson', 'w') as f:
    json.dump(valves, f)

