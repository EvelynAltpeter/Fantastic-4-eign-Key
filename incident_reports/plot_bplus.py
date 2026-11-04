
import csv
from collections import defaultdict
from statistics import median
import matplotlib.pyplot as plt

# Load benchmark results
groups = defaultdict(list)

with open("results/timings.csv", newline="") as f:
    for row in csv.DictReader(f):
        if (
            row["experiment"] == "E3_range_tempo"
            and row["index_type"] == "bplus_tree"
            and row["operation"] == "range"
            and row["code_version"] in ("dd70faa", "a0e890d")
        ):
            key = (row["code_version"], float(row["operation_param"]))
            groups[key].append(
                int(row["total_ns"]) / int(row["n_ops"]) / 1_000_000
            )

selectivities = sorted({s for _, s in groups})
versions = [
    ("dd70faa", "Before fix"),
    ("a0e890d", "After fix"),
]

plt.figure(figsize=(9, 5))

for version, label in versions:
    x = [s for s in selectivities if (version, s) in groups]
    y = [median(groups[(version, s)]) for s in x]
    plt.plot(x, y, marker="o", label=label)

plt.xlabel("Range selectivity")
plt.ylabel("Median query time (ms)")
plt.title("B+ Tree Range Search: Before vs After Fix")
plt.legend()
plt.grid(True, alpha=0.3)
plt.tight_layout()

plt.savefig(
    "incident_reports/figures/INC-02-performance.png",
    dpi=200
)

print("Graph saved successfully!")
