"""epub 完整性检查：泄漏/格式/翻译残留。

用法:
  python3 bin/verify_epub.py books/<书名>      # 从 chapters/ 检查源 md
  python3 bin/verify_epub.py path/to/file.epub # 直接检查 epub
"""
from __future__ import annotations
import argparse, re, sys, zipfile
from pathlib import Path


def check_md(md_files: list) -> dict:
    issues = {"page_sep": [], "latex": [], "img_html": [], "french_long": []}
    for f in md_files:
        text = f.read_text(encoding="utf-8")
        # 页分隔符
        for m in re.finditer(r"<!--\s*page:\s*\d+\s*-->", text):
            issues["page_sep"].append(f"{f.name}: '{m.group()}'")
        # LaTeX 残留
        for m in re.finditer(r"\$\s*\^\{[^}]+\}\s*\$|\$\^\{[^}]+\}\$", text):
            issues["latex"].append(f"{f.name}: '{m.group()}'")
        # 未转 <img>
        for m in re.finditer(r"<img[^>]*?/>", text):
            issues["img_html"].append(f"{f.name}: '{m.group()[:80]}'")
        # 长段法语（>=200 连续字符含 30+ 法语字母）
        for m in re.finditer(r"[a-zéèàùâêîôûçïüÿ]{30,}", text):
            issues["french_long"].append(f"{f.name}: '{m.group()[:60]}...'")
    return issues


def check_epub(epub: Path) -> dict:
    issues = {"page_sep": [], "latex": [], "french_long": []}
    with zipfile.ZipFile(epub) as z:
        for name in z.namelist():
            if not name.endswith(".xhtml"): continue
            c = z.read(name).decode("utf-8")
            for m in re.finditer(r"<!--\s*page:\s*\d+\s*-->", c):
                issues["page_sep"].append(f"{name}: '{m.group()}'")
            for m in re.finditer(r"\$\s*\^\{[^}]+\}\s*\$|\$\^\{[^}]+\}\$", c):
                issues["latex"].append(f"{name}: '{m.group()}'")
            text = re.sub(r"<[^>]+>", " ", c)
            for m in re.finditer(r"[a-zéèàùâêîôûçïüÿ]{30,}", text):
                issues["french_long"].append(f"{name}: '{m.group()[:60]}'")
    return issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", type=Path)
    a = ap.parse_args()
    if a.target.suffix == ".epub":
        issues = check_epub(a.target)
    elif a.target.is_dir():
        issues = check_md(list((a.target / "chapters").glob("*.md")))
    else:
        sys.exit("target must be .epub file or book directory")
    total = sum(len(v) for v in issues.values())
    print(f"\n{'='*50}")
    if total == 0:
        print(f"✅ {a.target} 全部检查通过")
    else:
        print(f"⚠️ {a.target} 发现 {total} 个问题：")
        for kind, items in issues.items():
            if items:
                print(f"\n  [{kind}] {len(items)} 个：")
                for it in items[:5]:
                    print(f"    {it}")
                if len(items) > 5:
                    print(f"    ... 还有 {len(items)-5} 个")
    return total


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
