"""Command-line interface: compress, decompress, and report compression stats."""

from __future__ import annotations

import argparse
import os
import sys

from .codec import CorruptArchiveError, compress, decompress


def _default_output(path: str, new_ext: str) -> str:
    base, _ = os.path.splitext(path)
    return base + new_ext


def cmd_compress(args: argparse.Namespace) -> int:
    with open(args.input, "rb") as fh:
        data = fh.read()
    archive = compress(data)
    out = args.output or _default_output(args.input, ".huf")
    with open(out, "wb") as fh:
        fh.write(archive)
    if not args.quiet:
        ratio = len(archive) / len(data) if data else 0.0
        print(f"{args.input} ({len(data)} B) -> {out} ({len(archive)} B), "
              f"ratio {ratio:.2%}")
    return 0


def cmd_decompress(args: argparse.Namespace) -> int:
    with open(args.input, "rb") as fh:
        archive = fh.read()
    try:
        data = decompress(archive)
    except CorruptArchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = args.output or _default_output(args.input, ".out")
    with open(out, "wb") as fh:
        fh.write(data)
    if not args.quiet:
        print(f"{args.input} -> {out} ({len(data)} B restored)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    with open(args.input, "rb") as fh:
        data = fh.read()
    archive = compress(data)
    ratio = len(archive) / len(data) if data else 0.0
    bits_per_symbol = len(archive) * 8 / len(data) if data else 0.0
    print(f"original:    {len(data):>10,} B")
    print(f"compressed:  {len(archive):>10,} B")
    print(f"ratio:       {ratio:>10.2%}")
    print(f"bits/symbol: {bits_per_symbol:>10.2f}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="huffman",
        description="Canonical Huffman compression of files (lossless).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("input", help="input file")
        p.add_argument("-o", "--output", default=None, help="output file")
        p.add_argument("-q", "--quiet", action="store_true", help="suppress output")

    c = sub.add_parser("compress", help="compress a file to .huf")
    add_common(c)
    c.set_defaults(func=cmd_compress)

    d = sub.add_parser("decompress", help="restore a .huf archive")
    add_common(d)
    d.set_defaults(func=cmd_decompress)

    s = sub.add_parser("stats", help="show compression stats without writing a file")
    s.add_argument("input", help="input file")
    s.set_defaults(func=cmd_stats)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
