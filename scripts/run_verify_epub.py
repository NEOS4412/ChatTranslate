#!/usr/bin/env python3
"""CLI: EPUB / Markdown 完整性校验（泄漏、格式、翻译残留）。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.verify_epub import check_epub, check_md


def main() -> int:
    ap = argparse.ArgumentParser(description="EPUB / Markdown 完整性校验")
    ap.add_argument("target", type=Path, help="书籍目录或 .epub 文件")
    args = ap.parse_args()

    target = args.target
    if target.suffix == ".epub":
        issues = check_epub(target)
    elif target.is_dir():
        chap_dir = target / "final"
        md_files = sorted(chap_dir.glob("*.md"))
        if not md_files:
            sys.exit(f"no markdown chapters found in {chap_dir}")
        issues = check_md(md_files)
    else:
        sys.exit("target must be .epub file or book directory")

    total = sum(len(v) for v in issues.values())
    print(f"\n{'='*50}")
    if total == 0:
        print(f"✅ {target} 全部检查通过")
    else:
        print(f"⚠️ {target} 发现 {total} 个问题：")
        for kind, items in issues.items():
            if items:
                print(f"\n  [{kind}] {len(items)} 个：")
                for it in items[:5]:
                    print(f"    {it}")
                if len(items) > 5:
                    print(f"    ... 还有 {len(items)-5} 个")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
