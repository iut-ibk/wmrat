import numpy as np
import datetime as dt
import os
import json
import sys
import copy
import numpy as np
import epanet_util as enu

def run(epanet_bin_path, epanet_inp_path, param_dict, output_dir):
    success, val = enu.epanet_inp_read(epanet_inp_path)
    if not success:
        print(f'fatal: {val}', file=sys.stderr)
        return False

    epanet_dict = val

    tmp_dir = output_dir + '/tmp'

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    if not os.path.exists(tmp_dir):
        os.makedirs(tmp_dir)

    # first run normal "base" simulation (without closed pipes)
    epanet_inp_base_path = tmp_dir + '/base.inp'
    enu.epanet_inp_write(epanet_dict, epanet_inp_base_path)

    epanet_rep_base_path = tmp_dir + '/base.rep'

    success, val = enu.run_epanet_and_collect_results(epanet_bin_path, epanet_inp_base_path, epanet_rep_base_path)
    if not success:
        print(f'{val}', file=sys.stderr)
        return False

    epanet_rep_dict = val

    below_threshold_base_cond = set()

    # check which nodes' pressure fall below threshold during normal conditions
    for node, node_results in epanet_rep_dict['nodes'].items():
        pressures = node_results['pressure']

        if np.min(pressures) < float(param_dict['min_required_pressure']):
            below_threshold_base_cond.add(node)

    #print(below_threshold_base_cond)

    n_pipes = len(epanet_dict['PIPES'])
    print(f'{dt.datetime.now()}: INFO: #pipes: {n_pipes}', file=sys.stderr)

    nodes_affected_by_pipe_failure = {}

    # then successively close pipes and rerun simulation to see how it affects the network
    for pipe_n, pipe_line in enumerate(epanet_dict['PIPES']):
        pipe_diameter = float(pipe_line[4])

        # skip too small pipes
        if pipe_diameter < float(param_dict['min_diameter_mm']):
            continue

        epanet_dict_tmp = copy.deepcopy(epanet_dict)

        pipe_name = pipe_line[0]

        if epanet_dict_tmp['PIPES'][pipe_n][-1] not in ['Open', 'Closed', 'CV']:
            print(f'EPANET input file anomaly: pipe must be "Open", "Closed" or "CV"', file=sys.stderr)
            return False

        epanet_dict_tmp['PIPES'][pipe_n][-1] = 'Closed'

        print(f'{pipe_name}: diameter = {pipe_diameter} [{pipe_n}/{n_pipes}]')

        epanet_inp_tmp_path = tmp_dir + f'/{pipe_name}_closed.inp'
        enu.epanet_inp_write(epanet_dict_tmp, epanet_inp_tmp_path)

        epanet_rep_tmp_path = tmp_dir + f'/{pipe_name}_closed.rep'

        success, val = enu.run_epanet_and_collect_results(epanet_bin_path, epanet_inp_tmp_path, epanet_rep_tmp_path)
        if not success:
            print(f'error: {val}', file=sys.stderr)
            return False

        epanet_rep_tmp_dict = val

        below_threshold = set()

        # check which nodes' pressure fall below threshold during normal conditions
        for node, node_results in epanet_rep_tmp_dict['nodes'].items():
            pressures = node_results['pressure']

            if np.min(pressures) < float(param_dict['min_required_pressure']):
                below_threshold.add(node)

        n_affected = len(below_threshold - below_threshold_base_cond)
        nodes_affected_by_pipe_failure[pipe_name] = n_affected
        print(f'#below_threshold = {len(below_threshold)}')

    nodes_affected_path = output_dir + '/nodes_affected_by_pipe_failure.json'
    with open(nodes_affected_path, 'w') as f:
        f.write(json.dumps(nodes_affected_by_pipe_failure))

    return True

