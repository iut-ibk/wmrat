#!/usr/bin/env python
import sys
import os
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

if 'EPANET_BIN_PATH' not in os.environ:
    print(f'fatal: EPANET_BIN_PATH not set', file=sys.stderr)
    sys.exit(1)

epanet_bin_path = os.environ['EPANET_BIN_PATH']

# parse param json
try:
    with open(json_path) as f:
        param_dict = json.load(f)

except Exception as e:
    print(f'fatal: error in parameter json: {e}', file=sys.stderr)
    sys.exit(1)

#TODO: probably branch here ...

# run scenario
success = pipe_criticality_analysis.run(epanet_bin_path, epanet_inp_path, param_dict, output_dir)

# something went wrong
if not success:
    print(f'fatal: analysis failed', file=sys.stderr)
    sys.exit(1)

# ... otherwise exit (0)

