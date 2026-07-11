#!/usr/bin/env python3
"""CLI: DeepSeek chapter translation."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.translate import run, MAX_TOKENS, CONCURRENCY

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="DeepSeek chapter translation")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", default="fr", choices=["en", "fr"])
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--workers", type=int, default=CONCURRENCY)
    a = ap.parse_args()
    run(a.book, a.src_lang, a.resume)
