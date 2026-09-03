import matplotlib.pyplot as plt
import json
import numpy as np
import os

os.makedirs('figures', exist_ok=True)
os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'

# 1. Timeline diagram of bitemporal concepts
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot([0, 100], [0, 0], color='black', linewidth=2)

ax.annotate('Policy v0 Effective', xy=(10, 0), xytext=(10, 0.5), arrowprops=dict(facecolor='black', shrink=0.05))
ax.annotate('Policy v1 Effective', xy=(40, 0), xytext=(40, 0.5), arrowprops=dict(facecolor='black', shrink=0.05))
ax.annotate('Policy v1 Enters DB\n(Recorded)', xy=(60, 0), xytext=(60, -0.7), arrowprops=dict(facecolor='red', shrink=0.05))

ax.set_xlim(0, 100)
ax.set_ylim(-1, 1)
ax.axis('off')
plt.title("Bitemporal Policy Evolution")
plt.tight_layout()
plt.savefig('figures/timeline.png')
plt.close()

# 2. S1 grouped bars with error bars
# Using the output values from stats.py for deepseek rs11
labels = ['floor_static_v0', 'latest_timestamp', 'plain_rag', 'full_history_brute', 'bitemporal_drift', 'oracle_expiry']
documented = [0.000, 1.000, 0.684, 0.711, 1.000, 1.000]
lagged = [0.000, 0.344, 0.492, 0.623, 0.590, 1.000]
rollback = [1.000, 0.000, 0.524, 0.476, 1.000, 1.000]

doc_err = [[0,0,0,0,0,0], [0,0,0.684-0.53,0.711-0.55,0,0]] # lower, upper? wait, plt.bar yerr requires 2xN array.
# I'll just use symmetric for simplicity or exact. 
doc_err = [
    [0.0, 0.0, 0.684-0.53, 0.711-0.55, 0.0, 0.0], # lower
    [0.0, 0.0, 0.82-0.684, 0.84-0.711, 0.0, 0.0]  # upper
]
lag_err = [
    [0.0, 0.344-0.23, 0.492-0.36, 0.623-0.51, 0.590-0.46, 0.0],
    [0.0, 0.46-0.344, 0.62-0.492, 0.74-0.623, 0.70-0.590, 0.0]
]
roll_err = [
    [0.0, 0.0, 0.524-0.33, 0.476-0.29, 0.0, 0.0],
    [0.0, 0.0, 0.71-0.524, 0.67-0.476, 0.0, 0.0]
]

x = np.arange(len(labels))
width = 0.25

fig, ax = plt.subplots(figsize=(12, 6))
rects1 = ax.bar(x - width, documented, width, yerr=doc_err, label='Documented', capsize=5)
rects2 = ax.bar(x, lagged, width, yerr=lag_err, label='Lagged', capsize=5)
rects3 = ax.bar(x + width, rollback, width, yerr=roll_err, label='Rollback', capsize=5)

ax.set_ylabel('Pass1 Rate')
ax.set_title('S1 Cell Performance by Condition')
ax.set_xticks(x)
ax.set_xticklabels(labels, rotation=15)
ax.legend()
plt.tight_layout()
plt.savefig('figures/s1_grouped.png')
plt.close()

# 3. Detector frontier from A6
with open('runs/a6_sweep.json', 'r') as f:
    a6 = json.load(f)
    
fig, ax = plt.subplots(figsize=(8, 6))

for m, v in a6.items():
    if "ADWIN" in m:
        ax.scatter(v['fpr'], v['mean_delay'], label=m, marker='o')
    else:
        ax.scatter(v['fpr'], v['mean_delay'], label=m, marker='x', s=100)

ax.set_xlabel('False Positive Rate')
ax.set_ylabel('Mean Delay (events)')
ax.set_title('Drift Detector Frontier')
# Put legend outside
box = ax.get_position()
ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
plt.grid(True)
plt.tight_layout()
plt.savefig('figures/detector_frontier.png')
plt.close()

