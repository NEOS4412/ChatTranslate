"""AI 校对：把 proofread/full_zh.md 喂给 DeepSeek，找段落错误拆分/翻译腔/漏译。

输出 suggestions.json，列出每处问题 + 建议修改。人工 / 自动脚本再应用。

用法：
  python3 bin/proofread.py books/<书名>
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"

SYSTEM = """你是一名资深中文文学编辑。请对照以下规则审查翻译后的中文 markdown：

1. 段落错误拆分：因 PDF 分页导致一个完整段落被切成两段且无意义换行。
2. 译者注粘连：注释、补充说明紧贴正文，缺少空行分隔。
3. 翻译腔严重：欧化句式（"它是一个..."、"对于...来说"等），建议改为自然中文。
4. 漏译错译：与常识不符、人名地名前后不一致。

只输出严格 JSON 数组，每项：
{"loc":"原文 20~60 字片段","issue":"问题类型","suggestion":"修改后版本","reason":"理由"}

若无问题，输出 []。不要解释，不要 markdown 围栏。"""

USER_TEMPLATE = """【待校对文本（节选）】
{chunk}
"""


def call_llm(messages, key):
    for i in range(1, 4):
        try:
            r = requests.post(API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": messages, "temperature": 0.2},
                timeout=180)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"[retry {i}] {e}"); time.sleep(3 * i)
    sys.exit("LLM failed after retries")


def chunk_text(text: str, max_chars: int = 8000) -> list:
    """按 <!-- page:N --> 分块，每块不超过 max_chars。"""
    parts = re.split(r"(<!-- page:\d+ -->)", text)
    chunks, cur = [], ""
    i = 0
    while i < len(parts):
        seg = parts[i]
        if (len(cur) + len(seg)) > max_chars and cur:
            chunks.append(cur); cur = seg
        else:
            cur += seg
        i += 1
    if cur: chunks.append(cur)
    return chunks


def run(book: Path) -> None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key: sys.exit("ERROR: DEEPSEEK_API_KEY not set")
    src = book / "proofread" / "full_zh.md"
    if not src.exists(): sys.exit("ERROR: run clean_md.py first")
    text = src.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    print(f"[plan] {len(chunks)} chunks, total {len(text)} chars")
    all_sugg = []
    for i, ck in enumerate(chunks, 1):
        print(f"[scan] chunk {i}/{len(chunks)} ({len(ck)} chars)")
        out = call_llm([
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": USER_TEMPLATE.format(chunk=ck)},
        ], key)
        # 容错解析：去掉 <think>...</think> 后再找 JSON 数组
        cleaned = re.sub(r"<think>.*?</think>", "", out, flags=re.S)
        m = re.search(r"\[.*\]", cleaned, re.S)
        if not m: print(f"  no JSON, raw: {out[:200]}"); continue
        try:
            items = json.loads(m.group())
        except Exception as e:
            # 尝试修复常见问题：未转义引号
            print(f"  parse fail (will retry with raw output kept): {e}"); continue
        print(f"  {len(items)} suggestions")
        all_sugg.extend(items)
    out = book / "proofread" / "suggestions.json"
    out.write_text(json.dumps(all_sugg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[done] {len(all_sugg)} total -> {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    run(ap.parse_args().book)
