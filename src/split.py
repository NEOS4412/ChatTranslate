"""把 full_zh.md 按 ## 标题拆成 chapters/ch_NNN.md，并生成 .book 配置。

约定:
  - 第一个 # 标题 = 书名
  - 首个 ## 标题之前的内容 = 扉页/版权/前言
  - 每个 ## 标题 = 一个章节
  - 最前面 N 个章节标为 ! (前置，不显示)；后续标为 + (正式章节)

用法:
  python3 bin/split_chapters.py books/<书名> --front 7
"""
from __future__ import annotations
import argparse, re
from pathlib import Path


def split(text: str) -> tuple:
    """返回 (title, front_matter, [(chapter_title, chapter_body), ...])"""
    lines = text.splitlines(keepends=True)
    # 找第一个 # 标题
    title_idx = -1
    for i, ln in enumerate(lines):
        if ln.startswith("# ") and not ln.startswith("## "):
            title_idx = i; break
    if title_idx < 0:
        title = "未命名"; body_start = 0
    else:
        title = lines[title_idx].lstrip("# ").strip()
        body_start = title_idx + 1

    # 在 body_start 之后按 ## 切分
    sections = []
    cur_title, cur_body = None, []
    in_section = False
    for i in range(body_start, len(lines)):
        ln = lines[i]
        if ln.startswith("## ") and not ln.startswith("### "):
            if in_section:
                sections.append((cur_title, "".join(cur_body).strip()))
            cur_title = ln.lstrip("# ").strip()
            cur_body = []
            in_section = True
        else:
            if in_section: cur_body.append(ln)
    if in_section:
        sections.append((cur_title, "".join(cur_body).strip()))

    # front_matter: body_start 到第一个 ## 之间
    front_lines = []
    for i in range(body_start, len(lines)):
        if lines[i].startswith("## ") and not lines[i].startswith("### "):
            break
        front_lines.append(lines[i])
    front_matter = "".join(front_lines).strip()

    return title, front_matter, sections


def safe_name(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", "_", s)
    return s[:60]


def run(book: Path, front: int, protect: bool = False) -> None:
    md = book / "proofread" / "full_zh.md"
    text = md.read_text(encoding="utf-8")
    title, front_matter, sections = split(text)
    print(f"[split] 书名: {title}")
    print(f"[split] 前置段落: {len(front_matter)} chars")
    print(f"[split] 章节: {len(sections)}")

    # 目录名提取作者
    # 约定：<书名>_<作者姓>_<作者名>，作者部分按最后两个 _ 切
    dir_name = book.name
    parts = dir_name.split("_")
    if len(parts) >= 3:
        # 最后两段是作者名（姓 + 名）
        author = " ".join(parts[-2:])
        book_title = "_".join(parts[:-2])
    elif len(parts) == 2:
        author = parts[1]; book_title = parts[0]
    else:
        book_title, author = dir_name, "未知"

    chap_dir = book / "final"
    chap_dir.mkdir(exist_ok=True)

    # collect existing manual chapters before writing
    existing_manual = {}
    if protect:
        for f in chap_dir.glob("*.md"):
            existing_manual[f.name] = f.read_text(encoding="utf-8")
        print(f"[protect] preserved {len(existing_manual)} existing chapters")

    # remove only auto-generated files (ch_NNN.md pattern), keep manual files
    for f in chap_dir.glob("ch_*.md"):
        if protect and f.name in existing_manual:
            continue
        f.unlink()

    chapter_files = []
    for i, (ch_title, ch_body) in enumerate(sections, 1):
        path = chap_dir / f"ch_{i:03d}.md"
        if protect and path.name in existing_manual:
            # restore preserved manual version
            path.write_text(existing_manual[path.name], encoding="utf-8")
            print(f"  [protect] kept {path.name} (manual)")
        else:
            path.write_text(f"# {ch_title}\n\n{ch_body}\n", encoding="utf-8")
        chapter_files.append((i, ch_title, path.name, i <= front))

    # front_matter 写入独立文件
    if front_matter.strip():
        front_path = chap_dir / "ch_000_front.md"
        front_path.write_text(f"<!-- 前置：扉页/版权/前言 -->\n\n{front_matter}\n", encoding="utf-8")
        print(f"[split] front: {front_path.name}")

    # 生成 .book 配置（路径相对 .book 文件本身）
    cover_rel = "cover.jpg"
    has_cover = (book / cover_rel).exists()

    book_cfg = book / f"{book.name}.book"
    # epub 文件名用全目录名（已含作者），避免重名
    safe_t = safe_name(dir_name)
    lines = [
        f"author: {author.replace('_', ' ')}",
        f"title: {book_title.replace('_', ' ')}",
        "lang: zh-CN",
    ]
    if has_cover:
        lines.append(f"cover: {cover_rel}")
    # epub 输出到全局 output/
    lines.append("output.base_path: ../..")
    lines.append(f"output.epub: output/{safe_t}.epub")
    lines.append("epub.version: 3")
    lines.append("")
    lines.append("# 前置（扉页/版权/前言，不显示在目录）")
    front_file = chap_dir / "ch_000_front.md"
    if front_file.exists():
        lines.append(f"! chapters/{front_file.name}")
    lines.append("")
    lines.append("# 正文章节")
    for i, ch_title, fname, is_front in chapter_files:
        prefix = "-" if is_front else "+"
        lines.append(f"{prefix} chapters/{fname}")
    lines.append("")
    book_cfg.write_text("\n".join(lines), encoding="utf-8")
    print(f"[split] config: {book_cfg}")

    print(f"[split] {len(chapter_files)} 章节写入 {chap_dir}")
