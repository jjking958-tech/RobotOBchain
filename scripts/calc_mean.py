import numpy as np

file_path = f'/home/luo/multi-robot-data-collection/data/byz_5/run_3/robot_0'
with open(f'{file_path}/blockchain_confirmed_votes.txt', "r") as f:
    votes = eval(f.readline())
with open(f'{file_path}/byzantine_robots.txt', "r") as f:
    byz = eval(f.readline())
byz = []
quality_list = []
for vote in votes:
    if vote[0] not in byz:
        quality_list.append(vote[1])
for i in range(len(quality_list)):
    q_cut = quality_list[:i+1]
    mean = np.mean(q_cut)
    se = np.std(q_cut)/np.sqrt(len(q_cut))
    print(f'mean={mean},se={se}')

