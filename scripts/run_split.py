#!/usr/bin/env python3
"""CLI: Split merged text into chapters."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.split import run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--front", type=int, default=7, help="前 N 个章节视为前置")
    ap.add_argument("--protect", action="store_true", help="保留已存在的章节文件")
    args = ap.parse_args()
    run(args.book, args.front, args.protect)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
