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

from datagen.synthetic import (
    random_keys,
    arrange,
    point_queries,
    range_queries,
)

SEED = 4300

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


def e7_duplicate_keys(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E7: Compare index performance with unique and duplicate keys."""

    columns = ("track_id", "track_genre", "popularity")

    for column in columns:
        pairs = key_value_pairs(tracks, column)
        keys = [key for key, _ in pairs]

        # Prepare the same queries for every index.
        hits = point_queries(keys, 500, hit_rate=1.0, seed=SEED)

        # Range queries are required for popularity.
        ranges = (
            range_queries(keys, 500, selectivity=0.01, seed=SEED)
            if column == "popularity"
            else None
        )

        print(f"E7: testing column {column}", flush=True)

        for name in ALL_INDEXES:
            for rep in range(reps):
                index = make_index(name)

                common = dict(
                    experiment="E7",
                    dataset="spotify",
                    key_column=column,
                    insert_order="file",
                    n_keys=len(pairs),
                    rep=rep,
                )

                # Measure index build time.
                build_ns = time_build(index, pairs)
                writer.record(
                    index, **common,
                    operation="build",
                    operation_param="",
                    n_ops=len(pairs),
                    total_ns=build_ns,
                )

                # Measure successful point lookups.
                index.reset_stats()
                hit_ns = time_batch(index.search, hits)
                writer.record(
                    index, **common,
                    operation="point_hit",
                    operation_param=1.0,
                    n_ops=len(hits),
                    total_ns=hit_ns,
                    height=index.structure_info().get("height", ""),
                )

                # Measure range queries on popularity.
                if ranges is not None:
                    index.reset_stats()
                    range_ns = time_batch(
                        lambda bounds: index.range_search(*bounds),
                        ranges,
                    )
                    writer.record(
                        index, **common,
                        operation="range",
                        operation_param=0.01,
                        n_ops=len(ranges),
                        total_ns=range_ns,
                        height=index.structure_info().get("height", ""),
                    )

            print(f"E7: {column} / {name} finished", flush=True)

    print("E7: all experiments finished", flush=True)

# E1-E4: Spotify workloads. Keep experiment names stable for ResultsWriter/checker.
# All queries are prepared before timing; each replicate uses a fresh index.
from datagen.synthetic import point_queries, range_queries, prefix_queries

SIZES = (1_000, 3_000, 10_000, 30_000, 60_000, 114_000)
N_QUERIES = 500


def _sizes(pairs):
    """Use six requested sizes, capped at the available Spotify row count."""
    return [n for n in SIZES if n <= len(pairs)]


def _common(experiment, column, n, rep):
    return dict(experiment=experiment, dataset="spotify", key_column=column,
                insert_order="file", n_keys=n, rep=rep)


def E1_build_memory(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E1: file-order track_id build scaling and index memory."""
    pairs = key_value_pairs(tracks, "track_id")
    for n in _sizes(pairs):
        subset = pairs[:n]
        for name in ALL_INDEXES:
            memory = build_memory_bytes(lambda name=name: make_index(name), subset)
            for rep in range(reps):
                index = make_index(name)
                index.reset_stats()
                ns = time_build(index, subset)
                writer.record(index, **_common("E1_build_memory", "track_id", n, rep),
                              operation="build", operation_param="", n_ops=n,
                              total_ns=ns, memory_bytes=memory,
                              height=index.structure_info().get("height", ""))
            print(f"  E1 n={n:,} {name} done", flush=True)

def E2_point_lookups(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E2: successful and unsuccessful track_id point lookups by size."""
    pairs = key_value_pairs(tracks, "track_id")
    for n in _sizes(pairs):
        subset = pairs[:n]
        keys = [key for key, _ in subset]
        workloads = {
            "point_hit": point_queries(keys, N_QUERIES, 1.0, seed=SEED + n),
            "point_miss": point_queries(keys, N_QUERIES, 0.0, seed=SEED + n),
        }
        for name in ALL_INDEXES:
            for rep in range(reps):
                index = make_index(name)
                time_build(index, subset)  # not part of lookup timing
                for operation, queries in workloads.items():
                    index.reset_stats()
                    ns = time_batch(index.search, queries)
                    writer.record(index, **_common("E2_point_lookups", "track_id", n, rep),
                                  operation=operation,
                                  operation_param=1.0 if operation == "point_hit" else 0.0,
                                  n_ops=len(queries), total_ns=ns,
                                  height=index.structure_info().get("height", ""))
            print(f"  E2 n={n:,} {name} done", flush=True)

def E3_range_tempo(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E3: tempo range selectivity on the complete Spotify dataset."""
    pairs = key_value_pairs(tracks, "tempo")
    keys = [key for key, _ in pairs]
    selectivities = (0.0001, 0.001, 0.01, 0.05, 0.1, 0.25)
    workloads = {s: range_queries(keys, N_QUERIES, s, seed=SEED + i)
                 for i, s in enumerate(selectivities)}
    for name in ALL_INDEXES:
        for rep in range(reps):
            index = make_index(name)
            time_build(index, pairs)
            for selectivity, ranges in workloads.items():
                index.reset_stats()
                ns = time_batch(lambda bounds: index.range_search(*bounds), ranges)
                writer.record(index, **_common("E3_range_tempo", "tempo", len(pairs), rep),
                              operation="range", operation_param=selectivity,
                              n_ops=len(ranges), total_ns=ns,
                              height=index.structure_info().get("height", ""))
        print(f"  E3 {name} done", flush=True)

def E4_prefix_titles(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E4: track_name prefix search for prefix lengths 1 through 5."""
    pairs = key_value_pairs(tracks, "track_name")
    keys = [key for key, _ in pairs]
    workloads = {length: prefix_queries(keys, N_QUERIES, length, seed=SEED + length)
                 for length in range(1, 6)}
    for name in ALL_INDEXES:
        for rep in range(reps):
            index = make_index(name)
            time_build(index, pairs)
            for length, prefixes in workloads.items():
                index.reset_stats()
                ns = time_batch(index.prefix_search, prefixes)
                writer.record(index, **_common("E4_prefix_titles", "track_name", len(pairs), rep),
                              operation="prefix", operation_param=length,
                              n_ops=len(prefixes), total_ns=ns,
                              height=index.structure_info().get("height", ""))
        print(f"  E4 {name} done", flush=True)


def E5_insertion_order(writer: ResultsWriter, tracks: list[dict], reps: int) -> None:
    """E5: insertion-order sensitivity on reproducible, distinct synthetic keys.

    Every index gets identical key sets, insertion orders, and hit queries.
    Record independent fresh-build and batched lookup measurements.
    """
    sizes = (1_000, 10_000, 100_000)
    orders = ("random", "sorted", "reversed", "nearly_sorted")

    for n in sizes:
        # Generate all workloads before either build or lookup timing.
        keys = random_keys(n, length=12,
                           alphabet="abcdefghijklmnopqrstuvwxyz0123456789",
                           seed=SEED + n)
        queries = point_queries(keys, N_QUERIES, hit_rate=1.0, seed=SEED + n + 1)

        for order in orders:
            ordered_keys = arrange(keys, order=order, seed=SEED + n + 2)
            pairs = [(key, row_id) for row_id, key in enumerate(ordered_keys)]

            for name in ALL_INDEXES:
                for rep in range(reps):
                    common = dict(experiment="E5_insertion_order",
                                  dataset="synthetic", key_column="synthetic_string",
                                  insert_order=order, n_keys=n, rep=rep)

                    index = make_index(name)
                    index.reset_stats()
                    build_ns = time_build(index, pairs)
                    # writer.record captures rotations/splits via index.stats.
                    writer.record(index, **common, operation="build",
                                  operation_param="", n_ops=n, total_ns=build_ns,
                                  height=index.structure_info().get("height", ""))

                    index.reset_stats()
                    lookup_ns = time_batch(index.search, queries)
                    writer.record(index, **common, operation="point_hit",
                                  operation_param=1.0, n_ops=len(queries),
                                  total_ns=lookup_ns,
                                  height=index.structure_info().get("height", ""))

                print(f"  E5 n={n:,} {order:<13} {name} done", flush=True)


# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    "e6": e6_bplus_orders,
    "e7": e7_duplicate_keys,
    "E1_build_memory": E1_build_memory,
    "E2_point_lookups": E2_point_lookups,
    "E3_range_tempo": E3_range_tempo,
    "E4_prefix_titles": E4_prefix_titles,
    "E5_insertion_order": E5_insertion_order,
}


def main(argv: Optional[Sequence[str]] = None) -> None:
    p = parser("Run your experiments.")
    p.add_argument("--only", choices=sorted(EXPERIMENTS),
                   help="run just this experiment")
    args = parse(p, argv)

    writer = writer_from_args(args)
    tracks = load_tracks()

    names = [args.only] if args.only else list(EXPERIMENTS)

    for name in names:
        print(f"{name}: {args.reps} reps, session {writer.session_id}", flush=True)
        started = time.perf_counter()

        # THIS LINE ACTUALLY RUNS THE EXPERIMENT
        EXPERIMENTS[name](writer, tracks, args.reps)

        print(
            f"{name} finished in {time.perf_counter() - started:.1f}s",
            flush=True,
        )


if __name__ == "__main__":
    main()



