"""epub 完整性检查：泄漏/格式/翻译残留。

用法:
  yt-verify-epub books/<书名>      # 从 final/ 检查源 md
  yt-verify-epub path/to/file.epub # 直接检查 epub
"""
from __future__ import annotations
import re
import zipfile
from pathlib import Path


PROMPT_RESIDUE = re.compile(
    r"【原文段落\s*#?\d*】|【待校对文本|【术语表】|<think>.*?</think>", re.S
)
PAGE_SEP = re.compile(r"<!--\s*page:\s*\d+\s*-->")
LATEX_RESIDUE = re.compile(r"\$\s*\^\{[^}]+\}\s*\$|\$\^\{[^}]+\}\$")
IMG_HTML = re.compile(r"<img[^>]*?/>")
FRENCH_LONG = re.compile(r"[a-zéèàùâêîôûçïüÿ]{30,}")


def _issue(text: str, pattern: re.Pattern, key: str, file_label: str, issues: dict) -> None:
    for m in pattern.finditer(text):
        line = text[: m.start()].count("\n") + 1
        snippet = m.group()[:60] + ("..." if len(m.group()) > 60 else "")
        if key == "french_long":
            issues[key].append(f"{file_label}: '{snippet}...'")
        elif key == "prompt_residue":
            issues[key].append(f"{file_label}: L{line}: '{snippet}'")
        else:
            issues[key].append(f"{file_label}: '{snippet}'")


def check_md(md_files: list) -> dict:
    issues = {
        "page_sep": [],
        "latex": [],
        "img_html": [],
        "french_long": [],
        "prompt_residue": [],
    }
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        label = f.name
        _issue(text, PAGE_SEP, "page_sep", label, issues)
        _issue(text, LATEX_RESIDUE, "latex", label, issues)
        _issue(text, IMG_HTML, "img_html", label, issues)
        _issue(text, FRENCH_LONG, "french_long", label, issues)
        _issue(text, PROMPT_RESIDUE, "prompt_residue", label, issues)
    return issues


def check_epub(epub: Path) -> dict:
    issues = {
        "page_sep": [],
        "latex": [],
        "french_long": [],
        "prompt_residue": [],
    }
    with zipfile.ZipFile(epub) as z:
        for name in z.namelist():
            if not name.endswith(".xhtml"):
                continue
            raw = z.read(name).decode("utf-8")
            _issue(raw, PAGE_SEP, "page_sep", name, issues)
            _issue(raw, LATEX_RESIDUE, "latex", name, issues)
            text_only = re.sub(r"<[^>]+>", " ", raw)
            _issue(text_only, FRENCH_LONG, "french_long", name, issues)
            _issue(raw, PROMPT_RESIDUE, "prompt_residue", name, issues)
    return issues
