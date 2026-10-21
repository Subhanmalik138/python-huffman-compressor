"""huffman — canonical Huffman compression with a small CLI."""

from .codec import CorruptArchiveError, compress, decompress

__all__ = ["compress", "decompress", "CorruptArchiveError"]
__version__ = "1.0.0"
