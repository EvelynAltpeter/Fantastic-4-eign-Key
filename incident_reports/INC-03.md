# INC-03: Sorted List Uses Linear Search Instead of Binary Search

## Summary

The Sorted List index had a performance bug in its search() method. Even though the index stores keys in sorted order, the original implementation searched through the keys one at a time. This resulted in O(n) lookup time instead of the expected O(log n). I fixed the problem by replacing the linear search with the existing binary search helper, _bisect_left().

## Detection

I identified the issue while examining the Sorted List implementation for Part D. Since the keys were already stored in sorted order, I expected point lookups to use binary search. However, the original search() method used a loop to check keys sequentially. I then ran the E2 point-lookup experiment before and after the fix to measure the performance difference.

## Expected vs. observed

The expected behavior was for Sorted List point lookups to have O(log n) time complexity. Binary search should require relatively few comparisons, even when the dataset becomes large.

The original implementation instead had O(n) lookup complexity because it scanned the sorted list sequentially. As the number of records increased, lookup times and comparison counts increased substantially.

## Evidence

I ran the E2_point_lookups experiment using the Spotify dataset on my MacBook, with five repetitions for each configuration. I compared the original implementation from commit dd70faa against the corrected implementation from commit 9ae426d.

At 114,000 records, the original implementation took 4,523.490 milliseconds for successful lookups and 9,549.804 milliseconds for unsuccessful lookups. After the fix, those times decreased to 4.313 milliseconds and 2.873 milliseconds, respectively.

The corrected implementation was approximately 1,049 times faster for successful lookups and 3,324 times faster for unsuccessful lookups at this dataset size.

The comparison counts also showed a major improvement. Before the fix, successful lookups averaged 43,515 comparisons per operation, while unsuccessful lookups averaged 89,741 comparisons. After the fix, successful lookups averaged 16.5 comparisons and unsuccessful lookups averaged 16 comparisons.

## Root cause

The problem was in indexes/sorted_list.py. The original search() method iterated through self._keys using a for loop. Although the loop could stop once it passed the target key, it still potentially examined a large portion of the list.

This was unnecessary because the implementation already included _bisect_left(), which performs binary search. The search method simply wasn't using it.

## Fix

I modified search() to call _bisect_left(key) to locate the position where the target key should appear. The method then checks whether that position contains the requested key and returns the corresponding values if it does. Otherwise, it returns an empty list.

This removes the sequential scan and changes the expected lookup complexity from O(n) to O(log n).

The fix was committed as 9ae426d with the message "Fix sorted list linear search performance bug."

## Verification

After implementing the fix, I ran make test, which completed with 168 tests passed and 3 skipped.

I also reran the E2 point-lookup benchmark using the corrected implementation. The results showed that lookup times remained relatively stable as the dataset increased from 1,000 to 114,000 records.

At 114,000 records, successful lookups averaged approximately 16.5 comparisons and unsuccessful lookups averaged 16 comparisons. These results are consistent with logarithmic search complexity.

## Impact on recommendations

Before the fix, Sorted List appeared to be a poor choice for point lookups because its search performance deteriorated significantly as the dataset grew.

After the fix, Sorted List became much more competitive for point-lookup workloads. However, inserting new keys into a sorted Python list can still require shifting existing elements, so insertion performance remains an important tradeoff.

The corrected results should be used when comparing Sorted List against other index implementations in the final recommendations.

## Why the tests didn't catch it

The original implementation returned the correct search results, so correctness tests could pass even though the algorithm was inefficient.

The problem was related to performance rather than functionality. Tests that checked whether searches returned the correct values would not necessarily detect that the implementation was performing a linear scan instead of binary search.

Benchmarking lookup performance across increasing dataset sizes and examining comparison counters made the problem visible.


