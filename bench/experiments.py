"""Your experiments.  *** YOU EXTEND THIS FILE. ***

Run one experiment, or all of them:

    make experiments MEMBER=alice MACHINE=alice-mbp                 # all
    make experiments MEMBER=alice MACHINE=alice-mbp ONLY=example     # one

``example_point_lookups`` below is the summer 2024 interns' one finished experiment, and it works. Copy its
pattern for each experiment the README asks for (E1-E6), and register each
new function in ``EXPERIMENTS`` at the bottom of this file.

The pattern, for every configuration you measure:
    1. prepare keys and queries OUTSIDE the timed region,
    2. build a fresh index (time it with ``time_build`` if build cost matters),
    3. ``index.reset_stats()``, then time one batch with ``time_batch``,
    4. ``writer.record(index, ...)`` one row,
    5. repeat for ``reps`` replicates.
"""

from __future__ import annotations

import random
import time
from typing import Callable, Optional, Sequence

from bench.cli import parse, parser, writer_from_args
from bench.results import ResultsWriter
from bench.timing import build_memory_bytes, time_batch, time_build
from indexes import ALL_INDEXES, make_index
from loaders.spotify import key_value_pairs, load_tracks

from datagen.synthetic import point_queries, range_queries

SEED = 4300


def example_point_lookups(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """Build cost and point-lookup (hit) cost on track_id as the index grows."""
    pairs = key_value_pairs(tracks, "track_id")  # file order
    rng = random.Random(SEED)

    for n in (1_000, 10_000, len(pairs)):
        subset = pairs[:n]
        queries = [key for key, _ in rng.sample(subset, 500)]  # every query is a hit

        for name in ALL_INDEXES:
            # Memory once per configuration (tracing is slow; never time it).
            memory = build_memory_bytes(lambda: make_index(name), subset)

            for rep in range(reps):
                common = dict(
                    experiment="example", dataset="spotify", key_column="track_id",
                    insert_order="file", n_keys=n, rep=rep,
                )

                index = make_index(name)
                ns = time_build(index, subset)
                writer.record(
                    index, **common, operation="build", operation_param="",
                    n_ops=n, total_ns=ns, memory_bytes=memory,
                )

                index.reset_stats()
                ns = time_batch(index.search, queries)
                writer.record(
                    index, **common, operation="point_hit", operation_param=1.0,
                    n_ops=len(queries), total_ns=ns,
                    height=index.structure_info().get("height", ""),
                )
            print(f"  n={n:>7,}  {name:<14} done", flush=True)

def e6_bplus_orders(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E6: Compare B+ tree orders for build, point, and range performance."""

    orders = (3, 4, 8, 16, 32, 64, 128, 256, 512)

    # Prepare data before timing.
    track_pairs = key_value_pairs(tracks, "track_id")
    tempo_pairs = key_value_pairs(tracks, "tempo")

    track_keys = [key for key, _ in track_pairs]
    tempo_keys = [key for key, _ in tempo_pairs]

    # Point lookups: hits and misses, with the same workload for every order.
    point_hits = point_queries(track_keys, 500, hit_rate=1.0, seed=SEED)
    point_misses = point_queries(track_keys, 500, hit_rate=0.0, seed=SEED)

    # Range queries: approximately 1% of distinct tempo keys per query.
    ranges = range_queries(tempo_keys, 500, selectivity=0.01, seed=SEED)

    for order in orders:
        print(f"E6: testing B+ tree order {order}", flush=True)

        for rep in range(reps):
            # Build a fresh tree using track_id.
            index = make_index("bplus_tree", order=order)

            common = dict(
                experiment="E6",
                dataset="spotify",
                key_column="track_id",
                insert_order="file",
                n_keys=len(track_pairs),
                rep=rep,
            )

            build_ns = time_build(index, track_pairs)

            writer.record(
                index, **common,
                operation="build",
                operation_param="",
                n_ops=len(track_pairs),
                total_ns=build_ns,
            )

            # Measure successful point lookups.
            index.reset_stats()
            hit_ns = time_batch(index.search, point_hits)

            writer.record(
                index, **common,
                operation="point_hit",
                operation_param=1.0,
                n_ops=len(point_hits),
                total_ns=hit_ns,
                height=index.structure_info().get("height", ""),
            )

            # Measure unsuccessful point lookups.
            index.reset_stats()
            miss_ns = time_batch(index.search, point_misses)

            writer.record(
                index, **common,
                operation="point_miss",
                operation_param=0.0,
                n_ops=len(point_misses),
                total_ns=miss_ns,
                height=index.structure_info().get("height", ""),
            )

            # Build a separate B+ tree indexed by tempo.
            tempo_index = make_index("bplus_tree", order=order)

            tempo_common = dict(
                experiment="E6",
                dataset="spotify",
                key_column="tempo",
                insert_order="file",
                n_keys=len(tempo_pairs),
                rep=rep,
            )

            tempo_build_ns = time_build(tempo_index, tempo_pairs)

            writer.record(
                tempo_index, **tempo_common,
                operation="build",
                operation_param="",
                n_ops=len(tempo_pairs),
                total_ns=tempo_build_ns,
            )

            # Measure range queries using the tempo index.
            tempo_index.reset_stats()

            range_ns = time_batch(
                lambda bounds: tempo_index.range_search(*bounds),
                ranges,
            )

            writer.record(
                tempo_index, **tempo_common,
                operation="range",
                operation_param=0.01,
                n_ops=len(ranges),
                total_ns=range_ns,
                height=tempo_index.structure_info().get("height", ""),
            )

        print(f"E6: order {order} finished", flush=True)

# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    "e6": e6_bplus_orders,
}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = parser("Run your experiments.")
    p.add_argument("--only", choices=sorted(EXPERIMENTS), help="run just this experiment")
    args = parse(p, argv)
    writer = writer_from_args(args)
    tracks = load_tracks()
    names = [args.only] if args.only else list(EXPERIMENTS)
    for name in names:
        print(f"{name}: {args.reps} reps, session {writer.session_id}", flush=True)
        started = time.perf_counter()
        EXPERIMENTS[name](writer, tracks, args.reps)
        print(f"{name}: finished in {time.perf_counter() - started:.1f}s", flush=True)


if __name__ == "__main__":
    main()
