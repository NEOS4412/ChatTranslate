#!/usr/bin/env python3
"""CLI: OCR PDF -> markdown pages."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.ocr import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="PaddleOCR PDF -> markdown")
    ap.add_argument("pdf", type=Path)
    ap.add_argument("book", type=Path)
    ap.add_argument("--lang", default="en", choices=["en", "fr"])
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    run(a.pdf, a.book, a.resume)
