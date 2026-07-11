#!/usr/bin/env python3
"""CLI: Final quality scan."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.scan import scan_book, fix_book

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="全本最终扫描+修复")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", choices=["en", "fr", "auto"], default="fr")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--fix", action="store_true", help="自动修复格式问题")
    ap.add_argument("--fix-translate", action="store_true")
    ap.add_argument("--fix-merge", action="store_true")
    a = ap.parse_args()
    if a.fix or a.fix_translate or a.fix_merge:
        fix_book(a.book, a.src_lang, a.workers, a.fix_merge, a.fix_translate)
    else:
        scan_book(a.book, a.src_lang, a.workers)
