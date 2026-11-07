"""Reproduce the E5 graphs and tables in PART_B_E5_REPORT.md.

Run from project root:
    python report/generate_e5_figures_tables.py

Requires: pandas, numpy, matplotlib (included in project requirements.txt).
Reads results/timings.csv; outputs into report/e5_generated/.
Does not rerun benchmarks or modify the original results.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'report' / 'e5_generated'
OUT.mkdir(parents=True, exist_ok=True)
ORDERS = ['random', 'sorted', 'reversed', 'nearly_sorted']
INDEXES = ['unsorted_list', 'sorted_list', 'hash_table', 'avl_tree',
           'bplus_tree', 'ref_dict', 'ref_bisect']
SIZES = [1000, 10000, 100000]

raw = pd.read_csv(ROOT / 'results' / 'timings.csv', low_memory=False)
e5 = raw.loc[(raw['experiment'] == 'E5_insertion_order') &
             (raw['member'] == 'trisha') &
             (raw['code_version'] == 'b36e595')].copy()
if len(e5) != 840:
    raise ValueError(f'Expected 840 clean-version E5 rows, got {len(e5)}')
for col in ['n_keys','n_ops','total_ns','height','rotations','splits']:
    e5[col] = pd.to_numeric(e5[col], errors='coerce')
e5['build_seconds'] = e5['total_ns'] / 1e9
e5['lookup_us'] = e5['total_ns'] / e5['n_ops'] / 1000

# Table 1: Build time at 100k; each cell = median of 5 replicates.
build = e5[(e5['operation'] == 'build') & (e5['n_keys'] == 100000)]
build_table = (build.pivot_table(index='index_type', columns='insert_order',
                                values='build_seconds', aggfunc='median')
                    .reindex(index=INDEXES, columns=ORDERS))
build_table.to_csv(OUT / 'E5_build_100k_table.csv', float_format='%.6f')

# Figure 1: Grouped bars, log-scale y axis.
fig, ax = plt.subplots(figsize=(11.5, 5.8))
x = np.arange(len(INDEXES))
w = 0.19
for j, order in enumerate(ORDERS):
    ax.bar(x + (j - 1.5)*w, build_table[order], width=w, label=order.replace('_',' '))
ax.set_xticks(x, INDEXES, rotation=25, ha='right')
ax.set_ylabel('Median total build time (seconds, log scale)')
ax.set_title('E5: Build time at 100,000 keys by insertion order')
ax.set_yscale('log')
ax.legend(ncol=4, fontsize=9)
ax.grid(axis='y', alpha=0.25, which='both')
fig.tight_layout()
fig.savefig(OUT / 'E5_build_100k.png', dpi=200)
plt.close(fig)

# Table 2: Tree height, rotations, splits. Each cell median of 5 reps.
avl = (build[build['index_type'] == 'avl_tree']
       .groupby('insert_order')[['height','rotations']].median())
bplus = (build[build['index_type'] == 'bplus_tree']
         .groupby('insert_order')[['height','splits']].median())
tree_table = pd.DataFrame({
    'AVL height': avl['height'], 'AVL rotations': avl['rotations'],
    'B+ height': bplus['height'], 'B+ splits': bplus['splits'],
}).reindex(ORDERS)
tree_table.to_csv(OUT / 'E5_tree_structure_100k_table.csv', float_format='%.0f')

# Table 3: Successful lookup by size for RANDOM insertion; 5 reps per cell.
lookup = e5[(e5['operation'] == 'point_hit') & (e5['insert_order'] == 'random')]
lookup_group = lookup.groupby(['index_type', 'n_keys'])['lookup_us']
lookup_median = (lookup_group.median().unstack('n_keys')
                 .reindex(index=INDEXES, columns=SIZES))
lookup_iqr_100k = (lookup[lookup['n_keys'] == 100000]
                   .groupby('index_type')['lookup_us']
                   .quantile([0.25,0.75]).unstack().reindex(INDEXES))
lookup_table = lookup_median.rename(columns={1000:'1k median (us)',
                                              10000:'10k median (us)',
                                              100000:'100k median (us)'})
lookup_table['100k Q1 (us)'] = lookup_iqr_100k[0.25]
lookup_table['100k Q3 (us)'] = lookup_iqr_100k[0.75]
lookup_table.to_csv(OUT / 'E5_lookup_table.csv', float_format='%.6f')

# Figure 2: Random insertion, log-log axes; batch times divided by n_ops.
fig, ax = plt.subplots(figsize=(10, 5.8))
for index in INDEXES:
    ax.plot(SIZES, lookup_median.loc[index].to_numpy(), marker='o', linewidth=2,
            label=index)
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xticks(SIZES, ['1k','10k','100k'])
ax.set_xlabel('Number of keys (log scale)')
ax.set_ylabel('Median time per successful lookup (microseconds, log scale)')
ax.set_title('E5: Successful lookup scaling (random insertion)')
ax.legend(ncol=2, fontsize=9)
ax.grid(alpha=0.25, which='both')
fig.tight_layout()
fig.savefig(OUT / 'E5_lookup_scaling.png', dpi=200)
plt.close(fig)

print('\nBUILD TIME, 100k (seconds):\n', build_table.round(3).to_string())
print('\nTREE STRUCTURE, 100k:\n', tree_table.to_string())
print('\nLOOKUP TIMES (microseconds):\n', lookup_table.round(3).to_string())
print('\nFiles written to:', OUT)
