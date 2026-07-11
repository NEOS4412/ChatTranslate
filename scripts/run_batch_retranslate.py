#!/usr/bin/env python3
"""CLI: Batch retranslate low-quality pages."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.batch_retranslate import scan_and_retranslate


def main() -> int:
    ap = argparse.ArgumentParser(description="批量重翻低质量翻译页")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", choices=["en", "fr"], default="fr")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
    scan_and_retranslate(args.book, args.src_lang, args.threshold, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
