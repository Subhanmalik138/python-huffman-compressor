"""Tests for the Huffman compressor: correctness, edge cases, and the CLI."""

import os
import random
import subprocess
import sys

import pytest

from huffman import CorruptArchiveError, compress, decompress
from huffman.codec import BitReader, BitWriter, _HEADER_STRUCT
from huffman.tree import (
    build_tree,
    canonical_codes,
    code_lengths,
    frequency_table,
)

HERE = os.path.dirname(os.path.abspath(__file__))


# --- Tree construction -----------------------------------------------------

def test_frequency_table_counts_all_symbols():
    freqs = frequency_table(bytes([0, 0, 1, 255, 255, 255]))
    assert freqs[0] == 2
    assert freqs[1] == 1
    assert freqs[255] == 3
    assert freqs[2] == 0
    assert len(freqs) == 256


def test_build_tree_empty_returns_none():
    assert build_tree([0] * 256) is None


def test_build_tree_single_symbol_gets_length_one():
    root = build_tree(frequency_table(b"aaaa"))
    assert root is not None
    lengths = code_lengths(root)
    assert lengths[ord("a")] == 1


def test_tree_is_optimal_classic_example():
    # Classic textbook frequencies: optimal weighted path length is known.
    freqs = [0] * 256
    freqs[ord("a")] = 45
    freqs[ord("b")] = 13
    freqs[ord("c")] = 12
    freqs[ord("d")] = 16
    freqs[ord("e")] = 9
    freqs[ord("f")] = 5
    root = build_tree(freqs)
    lengths = code_lengths(root)
    weighted = sum(freqs[i] * lengths[i] for i in range(256))
    assert weighted == 224  # optimal value for this distribution


def test_code_lengths_satisfy_kraft_inequality():
    freqs = frequency_table(os.urandom(4096))
    lengths = code_lengths(build_tree(freqs))
    kraft = sum(2.0 ** -length for length in lengths if length)
    assert kraft <= 1.0 + 1e-9


def test_canonical_codes_are_prefix_free():
    rng = random.Random(42)
    lengths = [rng.choice([0, 1, 2, 3, 4, 5, 6, 7]) for _ in range(256)]
    codes = canonical_codes(lengths)
    # After left-aligning each code word to 64 bits, prefixes become shared
    # leading bits; no code word may be a prefix of another.
    seen = set()
    for code, length in codes.values():
        for shorter in range(1, length):
            assert (code >> (length - shorter), shorter) not in seen
        seen.add((code, length))


# --- Bit I/O ----------------------------------------------------------------

def test_bit_writer_reader_round_trip():
    writer = BitWriter()
    words = [(0b101, 3), (0b1, 1), (0b11001010, 8), (0b0, 1)]
    for code, length in words:
        writer.write_bits(code, length)
    raw = writer.flush()
    reader = BitReader(raw)
    for code, length in words:
        got = 0
        for _ in range(length):
            got = (got << 1) | reader.read_bit()
        assert got == code


def test_bit_reader_raises_past_end():
    with pytest.raises(EOFError):
        BitReader(b"").read_bit()


def test_bit_writer_total_bits():
    writer = BitWriter()
    writer.write_bits(0b111, 3)
    assert writer.total_bits == 3
    writer.write_bits(0b1, 1)
    assert writer.total_bits == 4


# --- Codec round trips --------------------------------------------------------

@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"a",
        b"aaaaaaaaaa",
        b"The quick brown fox jumps over the lazy dog",
        os.urandom(2048),
        bytes(range(256)) * 8,
        b"\x00" * 100 + b"\xff" * 100,
    ],
)
def test_compress_decompress_round_trip(data):
    assert decompress(compress(data)) == data


def test_round_trip_large_pseudorandom_text():
    rng = random.Random(7)
    alphabet = b"etaoinshrdlu ETAOIN SHRDLU 0123456789\n"
    data = bytes(rng.choice(alphabet) for _ in range(50_000))
    archive = compress(data)
    assert len(archive) < len(data)  # compressible text must shrink
    assert decompress(archive) == data


def test_header_layout():
    archive = compress(b"hello")
    assert archive[:4] == b"HUF1"
    assert archive[4] == 1
    assert len(archive) >= _HEADER_STRUCT.size
    orig_len = _HEADER_STRUCT.unpack_from(archive)[-1]
    assert orig_len == 5


def test_decompress_rejects_bad_magic():
    archive = bytearray(compress(b"hello"))
    archive[0] = ord("X")
    with pytest.raises(CorruptArchiveError):
        decompress(bytes(archive))


def test_decompress_rejects_truncated_archive():
    with pytest.raises(CorruptArchiveError):
        decompress(compress(b"hello world")[:10])


def test_decompress_rejects_truncated_bitstream():
    archive = compress(os.urandom(512))
    with pytest.raises((CorruptArchiveError, EOFError)):
        decompress(archive[:-4])


def test_code_table_survives_serialization():
    # The decoder rebuilds codes from lengths only — spot-check agreement.
    data = b"abracadabra" * 50
    assert decompress(compress(data)) == data


# --- CLI ---------------------------------------------------------------------

def run_cli(*args):
    env = dict(os.environ, PYTHONPATH=os.path.join(HERE, "..", "src"))
    return subprocess.run(
        [sys.executable, "-m", "huffman.cli", *args],
        capture_output=True, text=True, env=env,
    )


def test_cli_compress_and_decompress(tmp_path):
    src = tmp_path / "novel.txt"
    src.write_bytes(b"It was the best of times, " * 200)
    r = run_cli("compress", str(src), "-o", str(tmp_path / "novel.huf"))
    assert r.returncode == 0
    out = tmp_path / "restored.txt"
    r = run_cli("decompress", str(tmp_path / "novel.huf"), "-o", str(out))
    assert r.returncode == 0
    assert out.read_bytes() == src.read_bytes()


def test_cli_stats_reports_ratio(tmp_path):
    src = tmp_path / "data.bin"
    src.write_bytes(b"aaaaabbbbbcccccdddddeeeee" * 100)
    r = run_cli("stats", str(src))
    assert r.returncode == 0
    assert "ratio:" in r.stdout
    assert "bits/symbol" in r.stdout


def test_cli_decompress_corrupt_file_returns_error(tmp_path):
    bad = tmp_path / "bad.huf"
    bad.write_bytes(b"not a huffman archive at all")
    r = run_cli("decompress", str(bad), "-o", str(tmp_path / "x.out"))
    assert r.returncode == 1
    assert "error:" in r.stderr
