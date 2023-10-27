

# Related files: EBCQ_functions.py, graph_editing.py, misc_light.py

import pandas as pd
from scipy.stats import spearmanr

def dataview (sorted_dict_G, sorted_dict_H, combi, count_less_than_zero, length_total):



              



        
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


    # Calculate ranks
    rank_G = pd.Series([merged_dict[key][0] for key in keys]).rank(method='min', ascending=False)
    rank_H = pd.Series([merged_dict[key][1] for key in keys]).rank(method='min', ascending=False)

    # Populate ranks_G and ranks_H lists
    ranks_G = list(rank_G)
    ranks_H = list(rank_H)




   
       

    
    df = pd.DataFrame()

    # Calculate Spearman's correlation coefficient
    spearman_coefficient, _ = spearmanr(rank_G, rank_H)
    df = pd.DataFrame({'Key': keys, 'Rank G': rank_G, 'Rank H': rank_H, 'Hydraulic Failure Vaule': sorted_dict_H})
    df_summary = pd.DataFrame({'Spearman Coefficient': [spearman_coefficient],'total combiantions': length_total, 'Graph_Deleted': count_less_than_zero, 'Hydraulic_Deleted': counter})

    # Save to Excel
    output_file = combi + 'data_summary.xlsx'
    with pd.ExcelWriter(output_file) as writer:
        df.to_excel(writer, sheet_name='Data')
        df_summary.to_excel(writer, sheet_name='Summary')

    


    
