#!/usr/bin/env python3
"""CLI: Batch retranslate low-quality pages."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.batch_retranslate import scan_and_retranslate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量重翻低质量翻译页")
    parser.add_argument("book", type=Path)
    parser.add_argument("--src-lang", choices=["en", "fr"], default="fr")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    scan_and_retranslate(args.book, args.src_lang, args.threshold, args.dry_run)
