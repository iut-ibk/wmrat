# Related files: EBCQ_functions.py, graph_editing.py, misc_light.py
import pandas as pd
from scipy.stats import spearmanr
import json

def dataview(sorted_dict_G, sorted_dict_H, combi, count_less_than_zero, length_total, target_path_data, target_path_summary, target_path_data_json):
    combi = str(combi)

    counter  = 0
    
    merged_dict = {}
    ranks_G = []
    ranks_H = []
    keys = []

    for key in sorted_dict_G.keys():
        if key in sorted_dict_H:
            value_G = round(sorted_dict_G[key], 2)
            value_H = round(sorted_dict_H[key], 2)

            if value_H != 0:
                merged_dict[key] = value_G, value_H
                keys.append(key)
            else:
                counter = counter + 1

    print(keys)
    print(type(keys))

    # Calculate ranks
    rank_G = pd.Series([merged_dict[key][0] for key in keys]).rank(method='min', ascending=False)
    rank_H = pd.Series([merged_dict[key][1] for key in keys]).rank(method='min', ascending=False)
    hyd_values_dict = pd.Series([merged_dict[key][1] for key in keys])

    # Populate ranks_G and ranks_H lists
    ranks_G = list(rank_G)
    ranks_H = list(rank_H)
    hyd_values = list(hyd_values_dict)

    df = pd.DataFrame()

    # Calculate Spearman's correlation coefficient
    spearman_coefficient, _ = spearmanr(rank_G, rank_H)
    df = pd.DataFrame({'Key': keys, 'Rank G': rank_G, 'Rank H': rank_H, 'Hydraulic Failure Value': hyd_values})
    df_summary = pd.DataFrame({'Spearman Coefficient': [spearman_coefficient], 'total combinations': length_total, 'Graph_Deleted': count_less_than_zero, 'Hydraulic_Deleted': counter})

    # Save to CSV
    df.to_csv(target_path_data)
    df_summary.to_csv(target_path_summary)

    # write info also to json
    l = []
    for i in range(len(keys)):
        l.append({
            'pipes': list(keys[i]),
            'rank_G': ranks_G[i],
            'rank_H': ranks_H[i],
            'hyd_failure': hyd_values[i],
        })

    with open(target_path_data_json, 'w') as f:
        f.write(json.dumps(l))

