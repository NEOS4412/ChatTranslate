#!/usr/bin/env python3
"""CLI: Final quality scan."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.scan import fix_book, scan_book


SEVERITY_RANK = {"error": 3, "warning": 2, "info": 1, "never": 0}


def should_fail(results: list[dict], fail_on: str) -> bool:
    threshold = SEVERITY_RANK[fail_on]
    if threshold == 0:
        return False
    for result in results:
        for issue in result["issues"]:
            if SEVERITY_RANK.get(issue["severity"], 0) >= threshold:
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="全本最终扫描+修复")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", choices=["en", "fr", "auto"], default="fr")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--fix", action="store_true", help="自动修复格式问题")
    ap.add_argument("--fix-translate", action="store_true")
    ap.add_argument("--fix-merge", action="store_true")
    ap.add_argument("--fail-on", choices=["error", "warning", "info", "never"], default="error")
    args = ap.parse_args()
    if args.fix or args.fix_translate or args.fix_merge:
        fix_book(args.book, args.src_lang, args.workers, args.fix_merge, args.fix_translate)
        return 0
    results = scan_book(args.book, args.src_lang, args.workers)
    return 1 if should_fail(results, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(main())
