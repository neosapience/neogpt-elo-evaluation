"""
Online Elo Computation and bootstrapping code from https://colab.research.google.com/drive/1lAQ9cKVErXI1rEYq7hTKNaCQ5Q8TzrI5?usp=sharing
"""

from tqdm import tqdm
import fire
import jsonlines 
from pathlib import Path
from collections import defaultdict
import pandas as pd

def get_id(path):
    return ".".join(path.split("/")[-1].split(".")[:-1])

def load_jsonl(path):
    with open(path,'r') as f:
        ret = [e for e in jsonlines.Reader(f).iter()]
    return ret    

def parent_dir(path):
    return Path(path).parent.absolute()


def compute_elo(battles, K=4, SCALE=400, BASE=10, INIT_RATING=1000):
    result_rating = dict()
    for k in ("comparison_1", "comparison_2", "comparison_3"): # elo for each aspacts
        rating = defaultdict(lambda: INIT_RATING)
        for rd, model_a, model_b, win in battles[['model_a', 'model_b', k]].itertuples():
            ra = rating[f"{model_a}_{k}"]
            rb = rating[f"{model_b}_{k}"]
            ea = 1 / (1 + BASE ** ((rb - ra) / SCALE))
            eb = 1 / (1 + BASE ** ((ra - rb) / SCALE))
            if win == model_a:
                sa = 1
            elif win == model_b:
                sa = 0
            elif win == "tie":
                sa = 0.5
            elif win == "parse_error":
                continue
            else:
                raise Exception(f"unexpected vote {win}")
            rating[f"{model_a}_{k}"] += K * (sa - ea)
            rating[f"{model_b}_{k}"] += K * (1 - sa - eb)
        result_rating.update(rating)
    
    return result_rating

def get_bootstrap_result(battles, func_compute_elo, num_round):
    rows = []
    for i in tqdm(range(num_round), desc="bootstrap"):
        rows.append(func_compute_elo(battles.sample(frac=1.0, replace=True)))
    df = pd.DataFrame(rows)
    return df[df.median().sort_values(ascending=False).index]

def is_valid_battle(battle):
    return all(f"comparison_{i}" in battle.keys() for i in range(1,4)) and all(isinstance(battle[f'comparison_{i}'], str) for i in range(1,4))

def main(
    src_file : str = "<battle_result_path>", # battle results to evaluate elo on.
    out_file : str = "<elo_path>", # jsonl containing elo scores of each model.
):
    battles = []
    for _src in src_file.split(","):
        battles += load_jsonl(_src)
    battles = [e for e in battles if is_valid_battle(e)]
    battle_df = pd.DataFrame(battles)

    battle_df['model_a'] = [l[0] for l in battle_df['all_players']]
    battle_df['model_b'] = [l[1] for l in battle_df['all_players']]

    # elo_dict = compute_elo(battle_df)
    bootstrap_elo_lu = get_bootstrap_result(battle_df, compute_elo, 1000)
    bootstrap_lu_median = bootstrap_elo_lu.median().reset_index().set_axis(["model", "rating"], axis=1)

    bootstrap_lu_median = dict(zip(bootstrap_lu_median['model'],bootstrap_lu_median['rating']))

    with open(out_file,'w') as f:
        with jsonlines.Writer(f) as writer:
            writer.write(bootstrap_lu_median)
            f.flush()
    

if __name__ == "__main__":
    fire.Fire(main)
