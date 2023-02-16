import sys
import json
import epanet_util as enu
import os

if len(sys.argv) != 2:
    print(f'usage: {sys.argv[0]} <source-epsg> <epanet-inp>', file=sys.stderr)
    sys.exit(1)

epanet_path = sys.argv[1]

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

epanet_dict = {
    'nodes': nodes,
    'links': links,
}

print(json.dumps(epanet_dict))

