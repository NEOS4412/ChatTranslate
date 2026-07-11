"""全本最终扫描脚本（多线程）。

检测项:
1. <!-- page:N --> 残留
2. 未翻译的外文段（法语/英语）
3. LaTeX 残留 ($...$)
4. 段内句间断行（同一段落被空行分割）
5. HTML 标记残留（<div>, <table> 等）
6. 孤立的上标字符 (¹²³⁴⁵⁶⁷⁸⁹⁰)

用法:
  python3 bin/scan_final.py books/<书名>                          # 仅扫描
  python3 bin/scan_final.py books/<书名> --fix                     # 扫描+自动修复
  python3 bin/scan_final.py books/<书名> --workers 10              # 10 并发
  python3 bin/scan_final.py books/<书名> --fix-merge               # 仅修复段间断行
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import defaultdict
import requests
import sys
from src.config import DEEPSEEK_API_URL, DEEPSEEK_MODEL

# ===== 检测规则 =====

def check_page_remnants(text: str) -> list[dict]:
    """检查 <!-- page:N --> 残留"""
    issues = []
    for m in re.finditer(r'<!--\s*page:\s*\d+\s*-->', text):
        pos = text[:m.start()].count('\n') + 1
        issues.append({"line": pos, "type": "page_remnant", "content": m.group(), "severity": "error"})
    return issues

def check_latex(text: str) -> list[dict]:
    """检查 LaTeX 残留 $...$"""
    issues = []
    for m in re.finditer(r'\$[^$]+\$', text):
        # 跳过数学符号如 $^{e}$ 等
        content = m.group()
        if re.match(r'\$\s*\^\{?[a-zA-Z0-9*]+\}?\s*\$', content):
            issues.append({
                "line": text[:m.start()].count('\n') + 1,
                "type": "latex_superscript",
                "content": content,
                "severity": "warning"
            })
        else:
            issues.append({
                "line": text[:m.start()].count('\n') + 1,
                "type": "latex_residue",
                "content": content,
                "severity": "error"
            })
    return issues

def check_untranslated(text: str, src_lang: str = "fr") -> list[dict]:
    """检查连续外文段落（没有中文字符的段落）"""
    issues = []
    paragraphs = text.split('\n\n')
    line_offset = 0
    for para in paragraphs:
        stripped = para.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('<!--'):
            line_offset += stripped.count('\n') + 2
            continue
        # 跳过纯 HTML 行
        if re.match(r'^\s*<', stripped):
            line_offset += stripped.count('\n') + 2
            continue
        # 跳过纯图片/表格
        if re.match(r'^\s*!\[', stripped) or re.match(r'^\s*<table', stripped, re.I):
            line_offset += stripped.count('\n') + 2
            continue
        # 检查是否有中文字符
        cn = len(re.findall(r'[\u4e00-\u9fff]', stripped))
        if cn == 0 and len(stripped) > 60:
            line = line_offset + 1
            issues.append({
                "line": line,
                "type": "untranslated",
                "content": stripped[:120] + ("..." if len(stripped) > 120 else ""),
                "severity": "error"
            })
        line_offset += stripped.count('\n') + 2
    return issues

def check_broken_paragraphs(text: str) -> list[dict]:
    """检查段内句间断行：判断哪些段落其实应该合并"""
    issues = []
    lines = text.split('\n')
    for i in range(len(lines) - 1):
        curr = lines[i].strip()
        next_line = lines[i + 1].strip()
        # 空行 + 下一行不是标题/空行/列表/图片，且当前行以中文句号/问号/感叹号/引号结束但下一行是小写字母
        if curr == '' and next_line:
            # 找空行前的行
            j = i - 1
            while j >= 0 and lines[j].strip() == '':
                j -= 1
            if j >= 0:
                prev = lines[j].strip()
                # 如果前一行以中文标点结束且下一行以中文或小写字母开头 → 可能是断句
                if (re.search(r'[，。？！；：」"」]\s*$', prev) and
                    re.search(r'^[a-z\u4e00-\u9fff（「"\[{]', next_line)):
                    issues.append({
                        "line": j + 1,
                        "type": "broken_paragraph",
                        "content": f"...{prev[-30:]} | {next_line[:60]}...",
                        "severity": "info"
                    })
    return issues

def check_html_residue(text: str) -> list[dict]:
    """检查 HTML 标签残留 (除了 img)"""
    issues = []
    for m in re.finditer(r'</?(div|span|font|br|p|center|b|i|u)\b[^>]*>', text, re.I):
        issues.append({
            "line": text[:m.start()].count('\n') + 1,
            "type": "html_residue",
            "content": m.group(),
            "severity": "warning"
        })
    return issues

def check_superscript_chars(text: str) -> list[dict]:
    """检查孤立上标字符"""
    issues = []
    for m in re.finditer(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', text):
        issues.append({
            "line": text[:m.start()].count('\n') + 1,
            "type": "superscript_char",
            "content": m.group(),
            "severity": "warning"
        })
    return issues


def check_prompt_residue(text: str) -> list[dict]:
    """检查 LLM 提示词/中间处理标记是否泄漏到成品。"""
    patterns = [
        r"【原文段落\s*#?\d*】",
        r"【待校对文本",
        r"【术语表】",
        r"<think>.*?</think>",
    ]
    issues = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.S):
            issues.append({
                "line": text[:m.start()].count('\n') + 1,
                "type": "prompt_residue",
                "content": m.group()[:120],
                "severity": "error"
            })
    return issues

def scan_file(filepath: Path, src_lang: str = "fr") -> dict:
    """对单个文件运行所有检测"""
    text = filepath.read_text(encoding="utf-8")
    all_issues = []
    all_issues.extend(check_page_remnants(text))
    all_issues.extend(check_latex(text))
    all_issues.extend(check_untranslated(text, src_lang))
    all_issues.extend(check_broken_paragraphs(text))
    all_issues.extend(check_html_residue(text))
    all_issues.extend(check_superscript_chars(text))
    all_issues.extend(check_prompt_residue(text))
    return {"file": str(filepath.name), "issues": all_issues, "chars": len(text)}


def fix_issues(filepath: Path, src_lang: str = "fr", key: str | None = None, fix_merge: bool = False) -> dict:
    """自动修复文件中可修复的问题"""
    text = filepath.read_text(encoding="utf-8")
    orig = text
    changes = []

    # 1. 清理 <!-- page:N -->
    new_text, n = re.subn(r'<!--\s*page:\s*\d+\s*-->\n?', '', text)
    if n > 0:
        changes.append(f"removed {n} page remnants")

    # 2. 清理 LaTeX 上标 $^{X}$ / $^{e}$ / $^{*}$ / $^{e}$ 等
    new_text, n = re.subn(r'\$\s*\^\{?[a-zA-Z0-9*]+\}?\s*\$', '', new_text)
    if n > 0:
        changes.append(f"removed {n} LaTeX superscripts")

    # 3. 清理其他 LaTeX 残留
    new_text, n = re.subn(r'\$\s*\^\{[^}]+\}\s*\$', '', new_text)
    if n > 0:
        changes.append(f"removed {n} other LaTeX residues")

    # 4. 去掉多余的居中 div（保留内部内容）
    new_text = re.sub(r'<div\s+style="text-align:\s*center;">\s*', '', new_text)
    new_text = re.sub(r'\s*</div>', '', new_text)

    # 5. 段间断行合并（可选）
    if fix_merge:
        # 合并规则：空行两侧的行，如果上行以中文标点结尾且下行是中文/小写开头
        lines = new_text.split('\n')
        merged = []
        i = 0
        while i < len(lines):
            if i < len(lines) - 1 and lines[i].strip() == '' and merged:
                # 空行，检查是否需要合并
                prev_line = merged[-1] if merged else ''
                next_line = lines[i + 1].strip() if i + 1 < len(lines) else ''
                if (prev_line and next_line and
                    re.search(r'[，。？！；：」"」]\s*$', prev_line) and
                    re.search(r'^[a-z\u4e00-\u9fff（「"\[{]', next_line)):
                    # 合并：追加到前一行
                    merged[-1] = prev_line + ' ' + next_line
                    i += 2  # 跳过空行和下一行
                    continue
            merged.append(lines[i])
            i += 1
        new_text = '\n'.join(merged)
        # 清理连续空行
        new_text = re.sub(r'\n{3,}', '\n\n', new_text)
        changes.append(f"merged broken paragraphs")

    if new_text != orig:
        filepath.write_text(new_text, encoding="utf-8")
        changes.append(f"total {len(orig) - len(new_text)} chars removed")
        return {"file": str(filepath.name), "changed": True, "changes": changes}
    return {"file": str(filepath.name), "changed": False, "changes": []}


# ===== 翻译未翻译段（DeepSeek API） =====

def translate_paragraph(para: str, key: str, src_lang: str = "fr") -> str | None:
    """翻译一段外文"""
    sys_prompt = "你是一名专业翻译。将以下外文翻译成简体中文。只返回翻译结果，不要解释。如果原文过短（<10字）或看起来是专有名词/书名，保持原文不翻译。"
    user_prompt = f"语言：{src_lang}\n\n{para}"
    try:
        r = requests.post(DEEPSEEK_API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": "deepseek-v4-flash", "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ], "temperature": 0.3, "max_tokens": 2000, "reasoning_effort": "low"},
            timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"    [translate error] {e}")
        return None


def fix_untranslated_in_file(filepath: Path, key: str, src_lang: str = "fr", workers: int = 5) -> dict:
    """扫描并修复文件中的未翻译段落"""

    text = filepath.read_text(encoding="utf-8")
    orig = text

    # 找到需要翻译的段落
    paragraphs = text.split('\n\n')
    to_translate = []
    for i, para in enumerate(paragraphs):
        stripped = para.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('<!--'):
            continue
        if re.match(r'^\s*<', stripped) or re.match(r'^\s*!\[', stripped):
            continue
        cn = len(re.findall(r'[\u4e00-\u9fff]', stripped))
        if cn == 0 and len(stripped) > 60:
            to_translate.append((i, stripped))

    if not to_translate:
        return {"file": str(filepath.name), "fixed": 0, "total": 0}

    def do_translate(idx, para):
        result = translate_paragraph(para, key, src_lang)
        return idx, result

    fixed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(do_translate, idx, para): (idx, para) for idx, para in to_translate}
        for future in as_completed(futures):
            idx, result = future.result()
            if result:
                paragraphs[idx] = result
                fixed += 1

    if fixed > 0:
        new_text = '\n\n'.join(paragraphs)
        filepath.write_text(new_text, encoding="utf-8")
        return {"file": str(filepath.name), "fixed": fixed, "total": len(to_translate)}
    return {"file": str(filepath.name), "fixed": 0, "total": len(to_translate)}


def scan_book(book_dir: Path, src_lang: str = "fr", workers: int = 10) -> list:
    """扫描全书 chapters 目录"""
    chapters_dir = book_dir / "final"
    if not chapters_dir.exists():
        print(f"ERROR: {chapters_dir} not found")
        return []

    files = sorted(chapters_dir.glob("ch_*.md"))
    print(f"\n🔍 扫描全书 {len(files)} 章节（{workers} 并发）...\n")

    all_results = []
    total_issues = defaultdict(int)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(scan_file, f, src_lang): f for f in files}
        for future in as_completed(futures):
            result = future.result()
            all_results.append(result)
            fname = result["file"]
            issues = result["issues"]
            if issues:
                print(f"\n  📄 {fname} ({result['chars']} chars): {len(issues)} 个问题")
                severity_order = {"error": 0, "warning": 1, "info": 2}
                for issue in sorted(issues, key=lambda x: (severity_order.get(x["severity"], 9), x["line"])):
                    icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}
                    print(f"    {icon.get(issue['severity'], '•')} L{issue['line']}: [{issue['type']}] {issue['content'][:80]}")
                    total_issues[issue["type"]] += 1
            else:
                print(f"  ✅ {fname} ({result['chars']} chars): 干净")

    print(f"\n{'='*50}")
    print(f"📊 汇总:")
    for issue_type, count in sorted(total_issues.items(), key=lambda x: -x[1]):
        print(f"  {issue_type}: {count}")
    print(f"  总计: {sum(total_issues.values())} 个问题")
    return all_results


def fix_book(book_dir: Path, src_lang: str = "fr", workers: int = 5, fix_merge: bool = False,
             fix_translate: bool = False) -> None:
    """自动修复全书"""

    chapters_dir = book_dir / "final"
    files = sorted(chapters_dir.glob("ch_*.md"))

    key = os.environ.get("DEEPSEEK_API_KEY") if fix_translate else None
    if fix_translate and not key:
        print("ERROR: fix_translate 需要 DEEPSEEK_API_KEY")
        return

    print(f"\n🔧 自动修复 {len(files)} 章节...")

    # Phase 1: 格式修复（多线程）
    print(f"\n📋 Phase 1: 格式修复...")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fix_issues, f, src_lang, key, fix_merge): f for f in files}
        for future in as_completed(futures):
            result = future.result()
            if result["changed"]:
                print(f"  ✅ {result['file']}: {'; '.join(result['changes'])}")
            else:
                print(f"  ➖ {result['file']}: 无需修复")

    # Phase 2: 翻译未翻译段（串行避免API限流）
    if fix_translate:
        print(f"\n📋 Phase 2: 翻译未翻译段落...")
        for f in files:
            result = fix_untranslated_in_file(f, key, src_lang, workers=min(workers, 3))
            if result["fixed"] > 0:
                print(f"  ✅ {result['file']}: 翻译了 {result['fixed']}/{result['total']} 段")
            elif result["total"] > 0:
                print(f"  ⚠ {result['file']}: 尝试翻译 {result['total']} 段但全部失败")
            else:
                print(f"  ➖ {result['file']}: 无不翻译段落")

    # Phase 3: 清理连续空行
    print(f"\n📋 Phase 3: 清理多余空行...")
    for f in files:
        text = f.read_text(encoding="utf-8")
        new_text = re.sub(r'\n{3,}', '\n\n', text)
        new_text = re.sub(r'\n{2,}(\n#)', r'\n\1', new_text)
        if new_text != text:
            f.write_text(new_text, encoding="utf-8")
            print(f"  ✅ {f.name}: 清理多余空行")

    print(f"\n✅ 修复完成")
