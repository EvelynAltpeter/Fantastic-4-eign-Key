import csv
from collections import defaultdict
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt

BEFORE = Path("incident_reports/evidence/INC-01-before.csv")
AFTER = Path("results/timings.csv")
OUTPUT = Path("incident_reports/figures/INC-01-performance.png")

def load_data(path, version):
    groups = defaultdict(list)

    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if (
                row["experiment"] != "E5_insertion_order"
                or row["index_type"] != "avl_tree"
                or row["member"] != "trisha"
                or row["machine_id"] != "trisha-mbp"
                or row["code_version"] != version
                or row["operation"] != "build"
            ):
                continue

            key = (row["insert_order"], int(row["n_keys"]))
            groups[key].append(row)

    return {
        key: {
            "time_ms": median(
                int(r["total_ns"]) / 1_000_000
                for r in rows
            ),
            "rotations": median(
                int(r["rotations"]) for r in rows
            ),
            "height": median(
                int(r["height"]) for r in rows
            ),
        }
        for key, rows in groups.items()
    }

before = load_data(BEFORE, "unknown")
after = load_data(AFTER, "b36e595")

orders = ["sorted", "reversed", "random", "nearly_sorted"]
n = 100000

fig, axes = plt.subplots(1, 3, figsize=(17, 5))

metrics = [
    ("rotations", "Rotations"),
    ("height", "Tree height"),
    ("time_ms", "Build time (ms)"),
]

for ax, (metric, title) in zip(axes, metrics):
    x = range(len(orders))
    width = 0.35

    old = [before[(order, n)][metric] for order in orders]
    new = [after[(order, n)][metric] for order in orders]

    ax.bar(
        [i - width / 2 for i in x],
        old,
        width,
        label="Before (buggy)"
    )
    ax.bar(
        [i + width / 2 for i in x],
        new,
        width,
        label="After (fixed)"
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(orders, rotation=20)
    ax.set_title(title)
    ax.legend()

fig.suptitle("AVL E5 Before vs After — 100,000 Keys")
fig.tight_layout()

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUTPUT, dpi=180, bbox_inches="tight")

print("Saved:", OUTPUT)

for order in orders:
    old = before[(order, n)]
    new = after[(order, n)]

    print(
        f"{order}: "
        f"rotations {old['rotations']:.0f} -> {new['rotations']:.0f}, "
        f"height {old['height']:.0f} -> {new['height']:.0f}, "
        f"time {old['time_ms']:.2f} -> {new['time_ms']:.2f} ms"
    )
