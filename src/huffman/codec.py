"""Bit-level writer/reader plus the Huffman archive format.

Archive layout (little-endian):
    magic      4 bytes  b"HUF1"
    version    1 byte   0x01
    lengths    256 bytes  one code length per symbol (0 = unused)
    orig_len   8 bytes  original uncompressed size
    payload    variable   compressed bitstream (MSB-first), zero-padded to a byte
"""

from __future__ import annotations

import struct

from .tree import (
    build_tree,
    canonical_codes,
    code_lengths,
    frequency_table,
)

MAGIC = b"HUF1"
VERSION = 1
_HEADER_STRUCT = struct.Struct("<4sB256Bq")


class BitWriter:
    """Accumulates bits (MSB first) and flushes whole bytes."""

    def __init__(self) -> None:
        self._buffer = 0
        self._filled = 0
        self._bytes = bytearray()

    def write_bits(self, code: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            self._buffer = (self._buffer << 1) | ((code >> i) & 1)
            self._filled += 1
            if self._filled == 8:
                self._bytes.append(self._buffer)
                self._buffer = 0
                self._filled = 0

    def flush(self) -> bytes:
        if self._filled:
            self._bytes.append(self._buffer << (8 - self._filled))
            self._buffer = 0
            self._filled = 0
        return bytes(self._bytes)

    @property
    def total_bits(self) -> int:
        return len(self._bytes) * 8 + self._filled


class BitReader:
    """Reads bits MSB-first from a byte buffer."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_pos = 0
        self._bit_pos = 0

    def read_bit(self) -> int:
        if self._byte_pos >= len(self._data):
            raise EOFError("Bitstream ended before the archive was fully decoded")
        byte = self._data[self._byte_pos]
        bit = (byte >> (7 - self._bit_pos)) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bit_pos = 0
            self._byte_pos += 1
        return bit


class CorruptArchiveError(ValueError):
    """Raised when an archive's header or bitstream is invalid."""


def compress(data: bytes) -> bytes:
    """Compress ``data`` into a self-describing Huffman archive."""
    lengths = code_lengths(build_tree(frequency_table(data)))
    codes = canonical_codes(lengths)
    header = _HEADER_STRUCT.pack(MAGIC, VERSION, *lengths, len(data))

    writer = BitWriter()
    for byte in data:
        code, length = codes[byte]
        writer.write_bits(code, length)
    return header + writer.flush()


def _decode_tree(lengths: bytes) -> dict[tuple[int, int], int]:
    """Rebuild canonical codes as {(code, length): symbol} for the decoder."""
    return {
        (code, length): symbol
        for symbol, (code, length) in canonical_codes(list(lengths)).items()
    }


def decompress(archive: bytes) -> bytes:
    """Restore the original bytes from a Huffman archive."""
    if len(archive) < _HEADER_STRUCT.size:
        raise CorruptArchiveError("archive is shorter than its header")
    magic, version, *rest = _HEADER_STRUCT.unpack_from(archive)
    *lengths, orig_len = rest
    if magic != MAGIC:
        raise CorruptArchiveError(f"bad magic: {magic!r}")
    if version != VERSION:
        raise CorruptArchiveError(f"unsupported version: {version}")
    if orig_len < 0:
        raise CorruptArchiveError(f"negative original length: {orig_len}")

    table = _decode_tree(bytes(lengths))
    if orig_len and not table:
        raise CorruptArchiveError("non-empty archive with an empty code table")

    reader = BitReader(archive[_HEADER_STRUCT.size:])
    out = bytearray()
    code = 0
    length = 0
    while len(out) < orig_len:
        code = (code << 1) | reader.read_bit()
        length += 1
        symbol = table.get((code, length))
        if symbol is not None:
            out.append(symbol)
            code = 0
            length = 0
    return bytes(out)
