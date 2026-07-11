"""段间断行合并：把 PDF 分页导致的错误段落拆分合并回去。

规则（保守）：
- 段末不是句号/问号/感叹号/引号等终止标点
- 段末是中文/字母字符
- 段首不是标题/列表/编号/HTML
- 段首不是"X出版社"、"第X卷"等书目模式
- 段首字符是中文/字母

用法:
  python3 bin/merge_paragraphs.py books/<书名>
"""
from __future__ import annotations
import argparse, re
from pathlib import Path

PUB_YEAR = re.compile(r"(出版社|出版|印刷).{0,10}\d{2,4}年?$")
VOLUME = re.compile(r"(卷|册|部|集|篇)\s*[一二三四五六七八九十0-9]?\s*[：:]?\s*$")
SENT_END = set("。！？…」』)）.!?\"'")
SUBITEM_START = re.compile(r"^[a-zA-Z]\.\s|^[一二三四五六七八九十]\.\s|^\d+\.\s|^\(\d+\)|^（|^[a-z]\.\s")
TITLE_LIKE = re.compile(r"^《|^#|^「")
HTML_START = re.compile(r"^<|^!\[|^\[\^")


def is_subitem(text: str) -> bool:
    return bool(SUBITEM_START.match(text.strip()))


def is_pub_meta(text: str) -> bool:
    end = text.rstrip()[-30:]
    if PUB_YEAR.search(end): return True
    if VOLUME.search(end): return True
    if re.search(r"\d{2,4}\s*年\s*$", end): return True
    return False


def is_pub_header(text: str) -> bool:
    """段首是书目/书名结构"""
    line = text.lstrip()[:50]
    if re.match(r"^《", line): return True
    if re.search(r"出版社", line[:20]): return True
    if re.match(r"^与[一-龥]", line): return True
    if re.match(r"^第[一二三四五六七八九十0-9]+", line): return True
    return False


def is_mergable(cur: str, nxt: str) -> bool:
    if cur.startswith("#") or nxt.startswith("#"): return False
    if HTML_START.match(cur) or HTML_START.match(nxt): return False
    if is_subitem(nxt) or SUBITEM_START.match(cur): return False
    if TITLE_LIKE.match(cur) or TITLE_LIKE.match(nxt): return False
    if is_pub_meta(cur): return False
    if is_pub_header(nxt): return False
    last = cur.rstrip()[-1]
    if last in SENT_END or last in "》）」】* ": return False
    if not ('\u4e00' <= last <= '\u9fff' or last.isalpha()): return False
    first = nxt[0]
    if not ('\u4e00' <= first <= '\u9fff' or first.isalpha() or first in "\"'"): return False
    return True


def normalize_paragraphs(text: str) -> str:
    """压平段落内连续 3+ 换行为 2 个"""
    import re as _re
    return _re.sub(r"\n{3,}", "\n\n", text)


def merge_paragraphs(text: str) -> tuple:
    """返回 (merged_text, n_merged)"""
    text = normalize_paragraphs(text)
    paras = text.split("\n\n")
    # 合并相邻可合并的段
    merged_list = [paras[0]]
    n_merged = 0
    for nxt in paras[1:]:
        cur = merged_list[-1]
        if not cur.strip():
            merged_list[-1] = nxt
            continue
        if not nxt.strip():
            continue
        if is_mergable(cur, nxt):
            merged_list[-1] = cur.rstrip() + nxt.lstrip()
            n_merged += 1
        else:
            merged_list.append(nxt)
    return "\n\n".join(merged_list), n_merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    args = ap.parse_args()
    chap_dir = args.book / "chapters"
    files = sorted(chap_dir.glob("ch_*.md"))
    total = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        new_text, n = merge_paragraphs(text)
        if n > 0:
            f.write_text(new_text, encoding="utf-8")
            print(f"  ✓ {f.name}: 合并 {n} 段")
            total += n
    print(f"\n合计合并 {total} 段")


if __name__ == "__main__":
    main()
