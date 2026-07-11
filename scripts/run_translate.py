#!/usr/bin/env python3
"""CLI: DeepSeek chapter translation."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.translate import CONCURRENCY, MAX_TOKENS, run


def main() -> int:
    ap = argparse.ArgumentParser(description="DeepSeek chapter translation")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", default="fr", choices=["en", "fr"])
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--workers", type=int, default=CONCURRENCY)
    args = ap.parse_args()
    run(args.book, args.src_lang, args.resume, workers=args.workers, max_tokens=args.max_tokens)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
