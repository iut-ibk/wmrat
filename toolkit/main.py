#!/usr/bin/env python
import sys
import json
import time
import wntr

import pipe_criticality_analysis

if len(sys.argv) != 4:
    print(f'usage: {sys.argv[0]} <EPANET-input> <param-json> <outputdir>', file=sys.stderr)
    sys.exit(1)

epanet_inp_path = sys.argv[1]
json_path = sys.argv[2]
output_dir = sys.argv[3]

# parse param json
try:
    with open(json_path) as f:
        param_dict = json.load(f)

except Exception as e:
    print(f'fatal: error in parameter json: {e}', file=sys.stderr)
    sys.exit(1)

# parse EPANET input file (via WNTR)
try:
    wn = wntr.network.WaterNetworkModel(epanet_inp_path)
except Exception as e:
    print(f'fatal: error in EPANET input file: {e}', file=sys.stderr)
    sys.exit(1)

#TODO: probably branch here ...

# run scenario
err = pipe_criticality_analysis.run(wn, param_dict, output_dir)

# something went wrong
if err:
    print(f'fatal: {err}', file=sys.stderr)
    sys.exit(1)

# ... otherwise exit (0)

