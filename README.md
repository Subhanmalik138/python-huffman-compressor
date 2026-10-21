# Huffman Compressor

A lossless file compressor built from scratch in pure Python — canonical Huffman coding with bit-level I/O, a self-describing archive format, and a small CLI. Zero dependencies.

## The problem

Off-the-shelf compression is a black box. This project answers a concrete interview question: *how does prefix coding actually work, end to end?* It takes the algorithm from the textbook — greedy tree building, prefix codes, bit packing — and turns it into a working tool that compresses real files, with the edge cases (empty input, single-symbol input, corrupt archives) handled, not glossed over.

## How it works

1. **Frequency analysis** (`tree.frequency_table`) — count byte occurrences in the input.
2. **Greedy tree building** (`tree.build_tree`) — repeatedly merge the two least-frequent nodes using a min-heap. This produces the provably optimal prefix tree.
3. **Canonical codes** (`tree.canonical_codes`) — tree depths become code lengths, which are reassigned in canonical form. Only the 256 lengths need storing in the archive header; the decoder rebuilds identical codes. This also keeps the header a fixed 269 bytes regardless of alphabet size.
4. **Bit packing** (`codec.BitWriter` / `codec.BitReader`) — MSB-first bit I/O; the decoder walks `(code, length)` pairs and stops after exactly `original_length` symbols, so trailing padding bits are never misread.
5. **Archive format** — `magic("HUF1") | version | 256 code lengths | original length (int64) | bitstream`. Corrupt headers and truncated streams raise `CorruptArchiveError`, never silently decode garbage.

## Design decisions

- **Canonical codes instead of storing the tree.** Storing full tree structure would cost ~2 bytes per symbol; storing just code lengths costs exactly 1 byte per symbol and the decoder is deterministic. Simpler format, smaller header.
- **Stop-at-length decoding instead of an EOF symbol.** A dedicated end-of-stream symbol inflates every code table; decoding exactly `original_length` symbols avoids it and makes truncated archives fail loudly via `EOFError`.
- **Single-symbol files get a 1-bit code.** A one-symbol Huffman tree has depth 0, which is unencodable — the special case is handled explicitly so e.g. 10 KB of `a`s compresses to ~10 KB of zero bits plus the header.

## Usage

```bash
# compress
python -m huffman.cli compress novel.txt
# -> novel.huf  (reports original size, compressed size, ratio)

# decompress
python -m huffman.cli decompress novel.huf -o novel_restored.txt

# compression stats without writing a file
python -m huffman.cli stats novel.txt
```

Run from the repo root with `src` on the path:

```bash
PYTHONPATH=src python -m huffman.cli stats somefile.txt
```

Typical results on English text: ~55–60% of original size (~4.5 bits/symbol).

## Tests

```bash
pip install pytest
PYTHONPATH=src pytest tests/ -v
```

25 tests cover: optimal tree construction (verified against the classic 224 weighted-path-length example), the Kraft inequality, prefix-freeness of canonical codes, bit writer/reader round trips, compress→decompress round trips (empty input, single symbol, random bytes, all 256 symbols, 50 KB text), corrupt/truncated archive rejection, and the CLI end to end.

## Tech stack

- Python 3.12, standard library only (`heapq`, `struct`, `argparse`, `dataclasses`)
- pytest for the test suite
