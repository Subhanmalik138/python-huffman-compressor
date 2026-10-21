"""Canonical Huffman coding: tree construction, code generation, and bit I/O."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Iterable

SYMBOL_COUNT = 256  # one byte per symbol


@dataclass(order=True)
class _HeapEntry:
    freq: int
    order: int
    node: "Node" = field(compare=False)


class Node:
    """A node in the Huffman tree. Leaf nodes carry a symbol (0-255)."""

    __slots__ = ("freq", "symbol", "left", "right")

    def __init__(self, freq: int, symbol: int | None = None,
                 left: "Node | None" = None, right: "Node | None" = None):
        self.freq = freq
        self.symbol = symbol
        self.left = left
        self.right = right

    @property
    def is_leaf(self) -> bool:
        return self.symbol is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        if self.is_leaf:
            return f"Node(symbol={self.symbol!r}, freq={self.freq})"
        return f"Node(freq={self.freq})"


def frequency_table(data: bytes) -> list[int]:
    """Count byte frequencies in ``data``; returns 256 counters."""
    freqs = [0] * SYMBOL_COUNT
    for byte in data:
        freqs[byte] += 1
    return freqs


def build_tree(freqs: Iterable[int]) -> Node | None:
    """Build the optimal Huffman tree with the greedy two-queue-free heap method.

    Returns ``None`` for empty input.
    """
    counts = list(freqs)
    heap: list[_HeapEntry] = []
    for symbol, freq in enumerate(counts):
        if freq:
            heap.append(_HeapEntry(freq, symbol, Node(freq, symbol)))
    if not heap:
        return None
    heapq.heapify(heap)

    order = SYMBOL_COUNT
    while len(heap) > 1:
        left = heapq.heappop(heap).node
        right = heapq.heappop(heap).node
        order += 1
        parent = Node(left.freq + right.freq, left=left, right=right)
        heapq.heappush(heap, _HeapEntry(parent.freq, order, parent))
    return heap[0].node


def code_lengths(root: Node | None) -> list[int]:
    """Depth of every symbol in the tree = its code length.

    A single-symbol tree gets length 1 (there must be at least one bit).
    """
    lengths = [0] * SYMBOL_COUNT
    if root is None:
        return lengths

    def walk(node: Node, depth: int) -> None:
        if node.is_leaf:
            assert node.symbol is not None
            lengths[node.symbol] = max(depth, 1)
        else:
            assert node.left is not None and node.right is not None
            walk(node.left, depth + 1)
            walk(node.right, depth + 1)

    walk(root, 0)
    return lengths


def canonical_codes(lengths: list[int]) -> dict[int, tuple[int, int]]:
    """Turn code lengths into canonical prefix codes.

    Canonical form assigns codes in symbol order so the table itself can be
    stored as just the lengths — the decoder rebuilds the same codes.
    Returns ``{symbol: (code, length)}`` where code is the integer code word.
    """
    # Sort by (length, symbol); skip zero-length (unused) symbols.
    pairs = sorted(
        ((length, symbol) for symbol, length in enumerate(lengths) if length),
        key=lambda pair: (pair[0], pair[1]),
    )
    codes: dict[int, tuple[int, int]] = {}
    code = 0
    prev_length = 0
    for length, symbol in pairs:
        code <<= length - prev_length  # shift for longer codes
        codes[symbol] = (code, length)
        code += 1
        prev_length = length
    return codes
