#!/usr/bin/env python3
"""CLI: Merge broken paragraphs in final chapters."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.merge import merge_paragraphs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    args = ap.parse_args()

    chap_dir = args.book / "final"
    files = sorted(chap_dir.glob("ch_*.md"))
    if not files:
        raise SystemExit(f"ERROR: no ch_*.md in {chap_dir}")

    total = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        new_text, count = merge_paragraphs(text)
        if count:
            path.write_text(new_text, encoding="utf-8")
            print(f"  ✓ {path.name}: 合并 {count} 段")
            total += count
    print(f"\n合计合并 {total} 段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
