"""Synthetic keys and query workloads.  *** YOU IMPLEMENT THIS FILE. ***

Real data (Spotify) shows how the indexes behave on realistic keys.
Synthetic data lets you control one variable at a time: how many keys, what
order they arrive in, how many lookups hit vs miss, how wide a range is.

Rules for every function:

* Use ``rng = random.Random(seed)`` and draw all randomness from ``rng``, so
  the same seed always produces the same output (on any machine).
* Never modify the list you are given; return a new one.

``tests/test_synthetic.py`` checks each function against this spec. Run it
with ``make test``.
"""

from __future__ import annotations

import random
import string
from typing import Any, Optional, Sequence


# Implementation explanation:
# Generated random strings of a specified length and alphabet.
# Used a set to ensure all keys were unique, then shuffled them into random order.
def random_keys(
    n: int,
    length: int = 8,
    alphabet: str = string.ascii_lowercase,
    seed: Optional[int] = None,
) -> list[str]:
    """Return n distinct random strings in random order."""
    rng = random.Random(seed)
    if n > len(set(alphabet)) ** length:
        raise ValueError("Not enough unique strings")

    keys = set()
    while len(keys) < n:
        keys.add("".join(rng.choices(alphabet, k=length)))
    result = sorted(keys)
    rng.shuffle(result)
    return result


# Implementation explanation:
# Organized keys into four patterns: random, sorted, reversed, and nearly sorted.
# For nearly sorted data, I started with sorted keys and randomly swapped a specified fraction of positions.
def arrange(
    keys: Sequence[Any],
    order: str,
    seed: Optional[int] = None,
    swap_fraction: float = 0.05,
) -> list[Any]:
    """Return keys in the requested order."""
    rng = random.Random(seed)
    result = list(keys)

    if order == "random":
        rng.shuffle(result)
    elif order == "sorted":
        result.sort()
    elif order == "reversed":
        result.sort(reverse=True)
    elif order == "nearly_sorted":
        result.sort()
        for _ in range(round(swap_fraction * len(result))):
            i = rng.randrange(len(result))
            j = rng.randrange(len(result))
            result[i], result[j] = result[j], result[i]
    else:
        raise ValueError(f"Invalid order: {order}")

    return result


# Implementation explanation:
# Generated lookups with an exact hit rate.
# Hits were sampled from existing keys, while misses were randomly generated and checked to ensure they weren't already present.
def point_queries(
    keys: Sequence[str],
    n_queries: int,
    hit_rate: float,
    seed: Optional[int] = None,
) -> list[str]:
    """Generate exact hit/miss lookup workload."""
    rng = random.Random(seed)
    n_hits = round(n_queries * hit_rate)
    existing = set(keys)
    result = [rng.choice(keys) for _ in range(n_hits)]

    while len(result) < n_queries:
        key = rng.choice(keys)
        miss = "".join(rng.choices(string.ascii_lowercase, k=len(key)))
        if miss not in existing:
            result.append(miss)

    rng.shuffle(result)
    return result


# Implementation explanation:
# Sorted the distinct keys and randomly selected ranges containing exactly the requested fraction of keys.
def range_queries(
    keys: Sequence[Any],
    n_queries: int,
    selectivity: float,
    seed: Optional[int] = None,
) -> list[tuple[Any, Any]]:
    """Generate ranges covering exactly w distinct keys."""
    rng = random.Random(seed)
    distinct = sorted(set(keys))
    w = max(1, round(selectivity * len(distinct)))

    result = []
    for _ in range(n_queries):
        start = rng.randrange(len(distinct) - w + 1)
        result.append((distinct[start], distinct[start + w - 1]))

    return result


# Implementation explanation:
# Randomly selected existing keys and extracted prefixes of the specified length, guaranteeing that every prefix matched at least one key.
def prefix_queries(
    keys: Sequence[str],
    n_queries: int,
    prefix_length: int,
    seed: Optional[int] = None,
) -> list[str]:
    """Generate prefixes guaranteed to match existing keys."""
    rng = random.Random(seed)
    valid = [key for key in keys if len(key) >= prefix_length]

    return [
        rng.choice(valid)[:prefix_length]
        for _ in range(n_queries)
    ]