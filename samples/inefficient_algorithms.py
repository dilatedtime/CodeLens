"""Sample Inefficient Algorithms for CodeLens Optimization & Complexity Analysis.

Demonstrates algorithmic and performance anti-patterns:
- Exponential O(2^N) recursion without memoization
- Quadratic O(N^2) duplicate search
- Inefficient string concatenation in loop
- Unbounded resource leakage (missing context manager)
"""

import time


# 1. Exponential Complexity O(2^N) without dynamic programming
def fibonacci_naive(n: int) -> int:
    """Calculates nth Fibonacci number with O(2^N) time complexity."""
    if n <= 1:
        return n
    return fibonacci_naive(n - 1) + fibonacci_naive(n - 2)


# 2. Quadratic O(N^2) Membership Search
def find_common_elements(list_a: list, list_b: list) -> list:
    """Finds common elements using nested linear scans (O(A * B))."""
    common = []
    for item in list_a:
        # Linear membership test in list_b causes O(N^2) overall complexity
        if item in list_b and item not in common:
            common.append(item)
    return common


# 3. Inefficient In-Place String Concatenation in Loop (O(N^2) allocations)
def concatenate_logs(lines: list[str]) -> str:
    """Repeated string concatenation creates quadratic memory overhead."""
    result = ""
    for line in lines:
        result += line + "\n"
    return result


# 4. Resource Leakage: unclosed file descriptor
def export_metrics(filepath: str, data: str):
    """File handle is never closed or protected with a context manager."""
    f = open(filepath, "w")
    f.write(data)
    # Missing f.close() or with statement
