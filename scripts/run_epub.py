#!/usr/bin/env python3
"""CLI: Build EPUB via crowbook."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path


def build(book_dir: Path) -> bool:
    """Build EPUB from proofread/full_zh.md."""
    proof = book_dir / "proofread" / "full_zh.md"
    if not proof.exists():
        print(f"ERROR: {proof} not found")
        return False

    dir_name = book_dir.name
    parts = dir_name.rsplit("_", 2)
    if len(parts) >= 3:
        title = parts[0].replace("_", " ")
        author = " ".join(parts[1:])
    elif len(parts) == 2:
        title = parts[0].replace("_", " ")
        author = parts[1]
    else:
        title = dir_name
        author = "未知"

    cover = book_dir / "assets" / "cover.jpg"
    if not cover.exists():
        cover = book_dir / "cover.jpg"

    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    safe = dir_name.replace("/", "_").replace("\\", "_")
    epub_path = out_dir / f"{safe}.epub"

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    try:
        content = proof.read_text(encoding="utf-8")
        tmp.write(
            f"---\nauthor: {author}\ntitle: {title}\nlang: zh-CN\n"
            f"output: [epub]\nepub.version: 3\n"
            f"resources.base_path: {book_dir.resolve()}\n"
            + (f"cover: {cover.resolve()}\n" if cover.exists() else "")
            + "---\n\n"
            + content
        )
        tmp.flush()
        subprocess.run(["crowbook", "-s", tmp.name, "--set", f"output.epub={epub_path.resolve()}"], check=True)
        print(f"[done] {epub_path}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"ERROR: crowbook failed: {exc}")
        return False
    finally:
        tmp.close()
        os.unlink(tmp.name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path, help="书籍目录路径")
    args = ap.parse_args()
    return 0 if build(args.book) else 1


if __name__ == "__main__":
    raise SystemExit(main())
