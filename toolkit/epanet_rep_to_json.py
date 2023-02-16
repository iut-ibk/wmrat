import sys
import json
import epanet_util as enu
import os

if len(sys.argv) != 2:
    print(f'usage: {sys.argv[0]} <epanet-rep>', file=sys.stderr)
    sys.exit(1)

epanet_rep_path = sys.argv[1]

success, val = enu.epanet_rep_read(epanet_rep_path)
if not success:
    print(f'fatal: {val}', file=sys.stderr)
    sys.exit(1)

epanet_rep_dict = val

print(json.dumps(epanet_rep_dict))

