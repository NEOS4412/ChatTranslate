#!/usr/bin/env python3
"""CLI: Clean translated markdown."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.clean import run


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--titles", action="store_true", help="批量降一级章节标题")
    ap.add_argument("--superscripts", action="store_true", help="孤立上标补空格")
    args = ap.parse_args()
    run(args.book, args.titles, args.superscripts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
