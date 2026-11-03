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

# Register experiments here: name -> function(writer, tracks, reps).
EXPERIMENTS: dict[str, Callable[[ResultsWriter, list[dict], int], None]] = {
    "example": example_point_lookups,
    "E1_build_memory": E1_build_memory,
    "E2_point_lookups": E2_point_lookups,
    "E3_range_tempo": E3_range_tempo,
    "E4_prefix_titles": E4_prefix_titles,
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
