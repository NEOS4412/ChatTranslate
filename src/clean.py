"""批量清理翻译后 md：LaTeX / 双层 div / 标题层级 / 脚注 / 孤立上标。

只动格式，不动正文。用法：
  python3 bin/clean_md.py books/<书名>
"""
from __future__ import annotations
import argparse, re
from pathlib import Path

# 简单但实用的清理规则
RULES = [
    # 1. 去除孤立 $ 包裹的 LaTeX：$ ^{①} $ -> ①；$ \underline{X} $ -> *X*
    (re.compile(r"\$\s*\^\{([¹²³⁴⁵⁶⁷⁸⁹⁰])\}\s*\$"), r"\1"),
    (re.compile(r"\$\s*\\underline\{([^}]+)\}\s*\$"), r"*\1*"),
    (re.compile(r"\$\s*\\textit\{([^}]+)\}\s*\$"), r"*\1*"),
    (re.compile(r"\$\s*\\emph\{([^}]+)\}\s*\$"), r"*\1*"),
    # 1.5 $ ^{*}, $^{*}$, $^*$ 等上标星号（OCR 常见）
    (re.compile(r"\$\s*\^\s*\{\s*\*\s*\}\s*\$"), "*"),
    (re.compile(r"\$\s*\^\s*\*\s*\$"), "*"),
    (re.compile(r"\$\s*\^\{\*\}\s*\$"), "*"),
    # 2. 双层 <div style="text-align: center;"><div ...>X</div> </div> -> 单层
    (re.compile(
        r'<div style="text-align: center;"><div style="text-align: center;">(.*?)</div>\s*</div>',
        re.S), r'<div style="text-align: center;">\1</div>'),
    # 3. 错误脚注 [^[1]] -> [^1]
    (re.compile(r"\[\[\^(\w[-\w]*)\]\]"), r"[^\1]"),
    # 3.1 删除页分隔符 <!-- page:N -->
    (re.compile(r"<!--\s*page:\s*\d+\s*-->\n?"), ""),
    # 3.1.1 LLM 未脱壳的 prompt 标签（行级），例如 【原文段落 #245】
    (re.compile(r"^【原文段落\s*#?\d*】\s*\n", re.M), ""),
    (re.compile(r"<!--\s*page:\s*\d+\s*-->\n?"), ""),
    # 3.2 LaTeX 残留 $ ^{X} $ -> X（带或不带空格）
    (re.compile(r"\$\s*\^\{([a-zA-Z]+)\}\s*\$"), r"\1"),
    (re.compile(r"\$\^\{([a-zA-Z]+)\}\$"), r"\1"),
    # 3.3 形如 $^{X}$ 不带空格 -> X
    (re.compile(r"\$\^\{([a-z])\}\$"), r"\1"),

]


def clean_file(p: Path, fix_titles: bool, fix_superscripts: bool) -> int:
    text = p.read_text(encoding="utf-8")
    orig = text
    for pat, repl in RULES:
        text = pat.sub(repl, text)
    # HTML <img> -> markdown 图片
    def img_conv(m):
        src = re.search(r'src="([^"]+)"', m.group(0))
        alt = re.search(r'alt="([^"]*)"', m.group(0))
        if not src: return m.group(0)
        return f"![{alt.group(1) if alt else ''}]({src.group(1)})"
    text = re.sub(r'<img\s+[^>]*?/>', img_conv, text)
    # 把包着图片的居中 div 去掉，让图片变成段落级（standalone image）
    text = re.sub(r'<div\s+style="text-align:\s*center;">(![^\n]*\))</div>', r'\1', text)
    # 4. 标题层级：所有 # 第N章/Chapter N -> ## 第N章（首行书名除外）
    if fix_titles:
        # 找到第一个 # 标题，作为书名保留；从第二个 # 起批量降一级
        lines = text.splitlines(keepends=True)
        first_h1 = -1
        for i, ln in enumerate(lines):
            if ln.startswith("# ") and not ln.startswith("## "):
                first_h1 = i; break
        for i in range(len(lines)):
            if i == first_h1: continue
            if lines[i].startswith("# ") and not lines[i].startswith("## "):
                # 跳过页分隔符行
                if "<!-- page:" in lines[i]: continue
                lines[i] = "##" + lines[i][1:]
        text = "".join(lines)
    # 5. 孤立上标字符（可选，谨慎）
    if fix_superscripts:
        text = re.sub(r"([¹²³⁴⁵⁶⁷⁸⁹⁰])(?=[\u4e00-\u9fff])", r"\1 ", text)
    if text != orig:
        p.write_text(text, encoding="utf-8")
        return 1
    return 0


def run(book: Path, titles: bool, sups: bool) -> None:
    src = book / "translated"
    files = sorted(src.glob("chapters/ch_*.md"))
    if not files:
        print("no translated chapters found"); return
    # 合并再清（保留页分隔符），便于校对
    merged = book / "proofread" / "full_zh.md"
    merged.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for f in files:
        t = f.read_text(encoding="utf-8")
        parts.append(t)
    big = "\n\n".join(parts)
    merged.write_text(big, encoding="utf-8")
    changed = clean_file(merged, titles, sups)
    print(f"[clean] merged {len(files)} chapters -> {merged} ({'changed' if changed else 'no change'})")
