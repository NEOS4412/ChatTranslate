#!/usr/bin/env python3
"""CLI: OCR PDF -> markdown pages."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.ocr import run


def main() -> int:
    ap = argparse.ArgumentParser(description="PaddleOCR PDF -> markdown")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("book", type=Path)
    ap.add_argument("--lang", default="en", choices=["en", "fr"])
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    run(args.pdf, args.book, args.resume)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
