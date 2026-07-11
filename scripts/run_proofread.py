#!/usr/bin/env python3
"""CLI: AI proofreading suggestions."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.proofread import run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    args = ap.parse_args()
    run(args.book)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
