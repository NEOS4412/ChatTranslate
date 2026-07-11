"""并发扫描所有章节，找出未翻译/翻译不完整的部分。

策略：每章喂给 DeepSeek 一次，问"是否还有法语原文没翻译"。
并发 10，遇问题章节输出诊断。

用法：
  python3 bin/scan_untranslated.py books/<书名>
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
import sys
from src.config import DEEPSEEK_API_URL, DEEPSEEK_MODEL

CONCURRENCY = 10
MAX_RETRIES = 2

SYSTEM = """你是中法双语校对。请严格审查以下中文翻译 markdown，找出任何残留的未翻译法语原文。

判定规则：
1. 出现连续 30+ 字符的法语字母（带或不带标点），视为未翻译
2. 出现典型法语短语（"à la"、"et non"、"ne se réduit pas"、"c'est-à-dire" 等）整段保留，视为未翻译
3. 中法混杂段落（半中半法），视为翻译不完整

只输出严格 JSON：
{"has_untranslated": true/false, "locations": ["原文片段 30-80 字符"], "reason": "一句话原因"}

若无问题输出 {"has_untranslated": false}。不要其他文字。"""


def call_llm(text: str, key: str) -> dict:
    for i in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(DEEPSEEK_API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": DEEPSEEK_MODEL,
                      "messages": [
                          {"role": "system", "content": SYSTEM},
                          {"role": "user", "content": text[:6000]},
                      ],
                      "temperature": 0.1, "max_tokens": 800, "reasoning_effort": "low"},
                timeout=120)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"].get("content", "")
            if not content:
                time.sleep(2); continue
            # 清除 <think>
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.S)
            m = re.search(r"\{.*\}", content, re.S)
            if m:
                return json.loads(m.group())
        except Exception as e:
            print(f"  [retry {i}] {e}", file=sys.stderr)
            time.sleep(2 * i)
    return {"has_untranslated": False, "error": True}


def scan_chapter(chap_file: Path, key: str) -> dict:
    text = chap_file.read_text(encoding="utf-8")
    # 跳过太短的章节（标题/封面）
    if len(text.strip()) < 200:
        return {"file": chap_file.name, "has_untranslated": False, "skip": "too short"}
    result = call_llm(text, key)
    result["file"] = chap_file.name
    return result


def fix_translations(bad: list, chap_dir: Path) -> None:
    """批量翻译所有 bad 章节里的未翻译段"""
    FR_WORD = r"[a-zA-ZàâäéèêëïîôöùûüÿœæçÀÂÄÉÈÊËÏÎÔÖÙÛÜŸŒÆÇ]{2,}"
    FRAG_PAT = re.compile(r"(?:" + FR_WORD + r"[\s,.;:!?\-—" + chr(0x22) + chr(0x27) + r"«»()]+){8,}")

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    all_to_tr = []
    locations_by_file = {}
    for r in bad:
        f = chap_dir / r["file"]
        t = f.read_text(encoding="utf-8")
        for m in FRAG_PAT.finditer(t):
            s = m.group()
            if re.search(r"[一-鿿]", s): continue
            all_to_tr.append(s)
        locations_by_file[f.name] = (f, list(FRAG_PAT.finditer(t)))
    if not all_to_tr:
        print("无可修复内容")
        return
    print(f"\n[fix] 翻译 {len(all_to_tr)} 段法语残留...")
    combined = "\n\n[BREAK]\n\n".join(all_to_tr)
    rsp = requests.post(DEEPSEEK_API_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": DEEPSEEK_MODEL,
              "messages": [
                  {"role": "system", "content": "法语到简体中文翻译。只输出译文，保留段落结构，不要任何解释/思考/元评论。每段之间用 [BREAK] 分隔。"},
                  {"role": "user", "content": combined},
              ],
              "temperature": 0.3, "max_tokens": 6000, "reasoning_effort": "low"},
        timeout=600)
    rsp.raise_for_status()
    content = rsp.json()["choices"][0]["message"]["content"]
    translations = [s.strip() for s in content.split("[BREAK]")]
    print(f"  得到 {len(translations)} 段译文")

    i = 0
    for fname, (fpath, matches) in locations_by_file.items():
        t = fpath.read_text(encoding="utf-8")
        for j in reversed(range(len(matches))):
            m = matches[j]
            orig = m.group()
            zh = translations[i] if i < len(translations) else "[FAIL]"
            i += 1
            t = t[:m.start()] + zh + t[m.end():]
        fpath.write_text(t, encoding="utf-8")
        print(f"  ✓ {fname}: 修复 {len(matches)} 段")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--workers", type=int, default=CONCURRENCY)
    ap.add_argument("--fix", action="store_true", help="扫描后自动翻译并写回")
    a = ap.parse_args()

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        sys.exit("ERROR: DEEPSEEK_API_KEY not set")

    chap_dir = a.book / "final"
    files = sorted(chap_dir.glob("ch_*.md"))
    if not files:
        sys.exit(f"ERROR: no ch_*.md in {chap_dir}")

    print(f"[scan] {len(files)} chapters, concurrency={a.workers}")

    bad = []
    done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(scan_chapter, f, key): f for f in files}
        for fut in as_completed(futs):
            done += 1
            try:
                r = fut.result()
            except Exception as e:
                print(f"[{done}/{len(files)}] {futs[fut].name}: ERR {e}")
                continue
            tag = "❌" if r.get("has_untranslated") else "✅"
            err = " [error]" if r.get("error") else ""
            print(f"[{done}/{len(files)}] {tag} {r['file']}{err}")
            if r.get("has_untranslated"):
                bad.append(r)

    out = a.book / "untranslated_report.json"
    out.write_text(json.dumps(bad, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"扫描完成：{len(bad)}/{len(files)} 章节含未翻译片段")
    if bad:
        print(f"\n详细报告：{out}")
        print("\n需要修复的章节：")
        for r in bad:
            print(f"\n  📄 {r['file']}")
            print(f"     原因: {r.get('reason','?')}")
            for loc in r.get("locations", [])[:3]:
                print(f"     - {loc[:100]}")
    else:
        print("✅ 全部章节翻译完整！")

    if a.fix and bad:
        fix_translations(bad, chap_dir)
