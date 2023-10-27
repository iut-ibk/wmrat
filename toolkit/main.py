#!/usr/bin/env python
import sys
import os
import json
import time
import wntr

import analysis.single_pipe_failure_graph.run as single_pipe_failure_graph
import analysis.single_pipe_failure_epanet.run as single_pipe_failure_epanet
import analysis.segment_criticality.run as segment_criticality

if len(sys.argv) != 5:
    print(f'usage: {sys.argv[0]} <analysis-type> <epanet-input> <param-json> <outputdir>', file=sys.stderr)
    sys.exit(1)

analysis_type = sys.argv[1]
epanet_inp_path = sys.argv[2]
json_path = sys.argv[3]
output_dir = sys.argv[4]

# parse param json
try:
    with open(json_path) as f:
        param_dict = json.load(f)

except Exception as e:
    print(f'error: error in parameter json: {e}', file=sys.stderr)
    sys.exit(1)

if analysis_type == 'single_pipe_failure_graph':
    run = single_pipe_failure_graph.run
elif analysis_type == 'single_pipe_failure_epanet':
    run = single_pipe_failure_epanet.run
elif analysis_type == 'segment_criticality':
    run = segment_criticality.run
else:
    print(f'error: no such analysis: {analysis_type}', file=sys.stderr)
    sys.exit(1)

# run analysis
success = run(epanet_inp_path, param_dict, output_dir)

# something went wrong
if not success:
    print(f'error: analysis failed', file=sys.stderr)
    sys.exit(1)

# ... otherwise succeed

