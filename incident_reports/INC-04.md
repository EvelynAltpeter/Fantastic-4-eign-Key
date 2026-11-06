# INC-04: Hash Table Uses Inefficient Fixed-Size Resizing

## Summary

The Hash Table index had a performance issue in how it increased its capacity. Instead of doubling the number of buckets when the table became too full, the original implementation added only 1,024 buckets each time. This caused the table to resize repeatedly as the dataset grew, making insertions increasingly expensive. I fixed the issue by changing the resizing strategy to double the table's capacity.

## Detection

I identified the issue while examining the Hash Table implementation in indexes/hash_table.py. I noticed that the _grow() method increased the number of buckets by a fixed amount instead of using proportional growth. Since every resize requires moving the existing keys into a new set of buckets, I suspected this was causing unnecessary work during large insertions.

I examined the existing E1 build benchmark results and then ran the E1_build_memory experiment before and after making the change.

## Expected vs. observed

I expected the Hash Table to maintain efficient insertion performance as the number of keys increased. With geometric resizing, the table should grow less frequently, allowing insertions to have approximately O(1) amortized time under standard hashing assumptions.

The original implementation instead increased capacity by a fixed 1,024 buckets. As the dataset became larger, this caused increasingly frequent full-table rehashing relative to the amount of new data inserted. The cumulative resizing work could grow quadratically with the number of keys.

## Evidence

I ran the E1_build_memory experiment on my MacBook using the Spotify dataset, with five repetitions for each configuration. I compared the original implementation from commit dd70faa with the corrected implementation from commit ad2ef5c.

The results were:

| Number of keys | Before (ms) | After (ms) | Speedup | Resizes before | Resizes after |
|---|---|---|---|---|---|
| 1,000 | 2.175 | 2.257 | 1.0x | 2 | 8 |
| 3,000 | 7.513 | 6.499 | 1.2x | 4 | 9 |
| 10,000 | 46.106 | 24.062 | 1.9x | 13 | 11 |
| 30,000 | 440.715 | 88.551 | 5.0x | 37 | 13 |
| 60,000 | 1,467.116 | 185.076 | 7.9x | 68 | 14 |
| 114,000 | 4,460.684 | 289.158 | 15.4x | 117 | 14 |

At 114,000 records, the original implementation took approximately 4,461 milliseconds to build the index, while the corrected implementation took approximately 289 milliseconds. This was a 15.4 times improvement.

The number of resizes also decreased from 117 to 14. These results support the conclusion that repeated resizing was a major cause of the original performance problem.

## Root cause

The problem was in the _grow() method in indexes/hash_table.py. The original code calculated the new capacity by adding the constant GROWTH_STEP, which was set to 1,024.

Every time the table exceeded its maximum load factor, the _grow() method created a new bucket list and rehashed all existing entries. Since capacity increased by only a fixed amount, the table had to repeat this process many times as the number of keys grew.

This created unnecessary overhead during index construction.

## Fix

I changed the _grow() method so that the new capacity is calculated by multiplying the current number of buckets by two rather than adding 1,024.

The original line was:

new_capacity = len(self._buckets) + self.GROWTH_STEP

The corrected line is:

new_capacity = len(self._buckets) * 2

This allows the Hash Table to grow proportionally, reducing the number of expensive rehashing operations.

The fix was committed as ad2ef5c with the message "Fix hash table resizing performance bug."

## Verification

After making the change, I ran make test. All 168 tests passed, with 3 skipped.

I then reran the E1_build_memory experiment with five repetitions using the same machine and dataset as the original benchmark.

The corrected implementation showed substantially faster build times at larger dataset sizes. At 114,000 records, build time decreased by approximately 93.5%, and the number of resizes decreased from 117 to 14.

These results are consistent with the expected improvement from using geometric resizing.

## Impact on recommendations

Before the fix, the Hash Table had relatively poor build performance for large datasets because it repeatedly rehashed its existing keys.

After the fix, Hash Table construction became significantly more efficient, making it a stronger option for workloads involving large numbers of insertions and exact-key lookups.

However, Hash Tables still do not maintain sorted key order, so range and prefix searches require examining keys across the table. This remains an important limitation when comparing Hash Tables against sorted indexes.

The corrected benchmark results should be used when making the final index recommendations.

## Why the tests didn't catch it

The original resizing strategy did not cause incorrect results. The Hash Table could still insert and retrieve keys successfully, even though it was resizing inefficiently.

Because the issue affected performance rather than correctness, functional tests could pass without detecting the problem.

The performance issue became clear when comparing build times and resize counts across increasing dataset sizes in the E1 benchmark.
