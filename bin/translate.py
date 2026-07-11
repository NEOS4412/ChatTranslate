"""DeepSeek 翻译 v2：按章节翻译（不再逐页翻译）。

工作流:
  1. 合并 OCR 页面 → full_raw.md
  2. 按 `# ` 标题切分为章节
  3. 逐章翻译（保持跨页上下文连贯）
  4. 输出到 translated/chapters/ch_NNN_标题.md

用法:
  export DEEPSEEK_API_KEY=...
  python3 bin/translate.py books/<书名> --src-lang fr
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"
MAX_RETRIES = 3
CONCURRENCY = 5
MAX_TOKENS = 8000

SYSTEM_PROMPT = """你是一名专业的文学翻译，负责将原文（法语或英语）markdown 翻译成简体中文。

【严格规则】
1. 只翻译正文。下列元素必须原样保留，不要触碰：
   - 图片：![alt](path) 或 <img src="..." />
   - HTML 标签：<div ...>...</div>
   - LaTeX 公式：$...$
   - 脚注引用：[^1]、[^章节-序号]
   - markdown 标记：# 标题、列表、引用块、分隔线
2. 人名、地名、专业术语按【术语表】统一。
3. 保留段落结构：原文的空行 = 段落分隔，不要合并或拆分段落。
4. 保持跨段落连贯性，不要在章节边界处断句。
5. 输出严格 markdown，不加 ``` 围栏。
"""

USER_TEMPLATE = """【术语表】
{glossary}

【原文章节 {ch_label}】
{source}
"""


def call_llm(messages: list, key: str) -> str:
    for i in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(API_URL,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": messages,
                      "temperature": 0.3,
                      "max_tokens": MAX_TOKENS,
                      "reasoning_effort": "low"},
                timeout=300)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [retry {i}/{MAX_RETRIES}] {e}")
            if i == MAX_RETRIES:
                raise
            time.sleep(3 * i)


def build_glossary(book: Path, src_lang: str) -> dict:
    cache = book / "translated" / "_glossary.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    chapters = split_into_chapters(book / "ocr" / "full_raw.md")
    samples = []
    for c in chapters[:4]:
        body = re.sub(r'<!-- page:\d+ -->', '', c['body']).strip()
        if body:
            samples.append(body[:3000])
    sample = "\n\n".join(samples)[:15000]
    msg = [
        {"role": "system",
         "content": "从以下原文（{}）抽取重要专有名词（人名、地名、书名、术语），只输出严格JSON，格式为{{\"原文\":\"译名\"}}。不超过60条。".format(src_lang)},
        {"role": "user", "content": sample},
    ]
    out = call_llm(msg, os.environ["DEEPSEEK_API_KEY"])
    m = re.search(r"\{.*\}", out, re.S)
    glossary = json.loads(m.group()) if m else {}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(glossary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[glossary] {len(glossary)} terms")
    return glossary



def filter_chapters(chapters: list[dict], src_lang: str, key: str) -> list[dict]:
    """用 AI 判断每章是否是需要翻译的正文内容，过滤掉广告/出版社列表等"""
    if not key:
        return chapters
    keep = []
    for ch in chapters:
        body_sample = re.sub(r'<!-- page:\d+ -->', '', ch['body']).strip()[:800]
        if not body_sample:
            continue
        msg = [
            {"role": "system", "content": "判断以下原文片段是属于书籍正文，还是属于出版社广告、书籍推荐列表、版权信息等无关内容。只输出 JSON: {{\"keep\": true/false}}"},
            {"role": "user", "content": f"语言：{src_lang}\n\n{body_sample}"},
        ]
        try:
            out = call_llm(msg, key)
            m = re.search(r'\"keep\"\s*:\s*(true|false)', out, re.I)
            if m and m.group(1).lower() == 'false':
                print(f"  🗑️  过滤: {ch['title'][:50]}")
                continue
        except:
            pass
        keep.append(ch)
    filtered = len(chapters) - len(keep)
    if filtered:
        print(f"  [filter] 移除了 {filtered} 个无关章节")
    return keep

def split_into_chapters(raw_path: Path) -> list[dict]:
    """把 full_raw.md 按 # 标题切分成章节"""
    text = raw_path.read_text(encoding="utf-8")
    parts = re.split(r'(?m)^(?=# )', text)
    chapters = []
    for pn, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        lines = part.split('\n')
        title = lines[0].lstrip('# ').strip()
        body = '\n'.join(lines[1:]).strip()
        chapters.append({"idx": pn, "title": title, "body": body})
    return chapters


def translate_chapter(chapter: dict, glossary: dict, key: str) -> str:
    gloss_str = "\n".join(f"{k} -> {v}" for k, v in glossary.items()) or "（暂无）"
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",
         "content": USER_TEMPLATE.format(
             glossary=gloss_str,
             ch_label=f"#{chapter['idx']}: {chapter['title']}",
             source=chapter['body'])},
    ]
    result = call_llm(msgs, key)
    title_line = f"# {chapter['title']}"
    if title_line not in result:
        result = f"{title_line}\n\n{result}"
    return result


def run(book: Path, src_lang: str, resume: bool) -> None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        sys.exit("ERROR: DEEPSEEK_API_KEY not set")

    raw = book / "ocr" / "full_raw.md"
    if not raw.exists():
        sys.exit("ERROR: ocr/full_raw.md missing, run ocr_paddle.py first")

    glossary = build_glossary(book, src_lang)
    chapters = split_into_chapters(raw)

    # 跳过空章（如 <!-- page:0 --> 之前的无内容部分）
    chapters = [c for c in chapters if c['body'].strip()]
    # AI 过滤无关章节（书籍广告、出版社列表等）
    chapters = filter_chapters(chapters, src_lang, key)
    print(f"[plan] {len(chapters)} chapters to translate")

    out_dir = book / "translated" / "chapters"
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = []
    for ch in chapters:
        out = out_dir / f"ch_{ch['idx']:03d}_{safe_name(ch['title'])}.md"
        ch['path'] = out
        if resume and out.exists() and out.stat().st_size > 100:
            print(f"  ⏭️  ch_{ch['idx']:03d} {ch['title'][:40]} (已存在)")
            continue
        todo.append(ch)

    def task(ch: dict) -> tuple[int, int]:
        result = translate_chapter(ch, glossary, key)
        ch['path'].write_text(result, encoding="utf-8")
        return ch['idx'], len(result)

    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        futs = {ex.submit(task, ch): ch for ch in todo}
        for fut in as_completed(futs):
            try:
                idx, cc = fut.result()
                done += 1
                ch = futs[fut]
                print(f"  ✅ [{done}/{len(todo)}] ch_{idx:03d} {ch['title'][:40]} ({cc} chars)")
            except Exception as e:
                ch = futs[fut]
                print(f"  ❌ ch_{ch['idx']:03d}: {e}")

    print(f"\n📊 完成: {done}/{len(todo)} → {out_dir}")
    if done > 0:
        print(f"💡 下一步: python3 bin/clean_md.py {book} --titles")


def safe_name(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", "_", s)
    return s[:60]


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="DeepSeek 逐章翻译（v2，推荐）")
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", default="fr", choices=["en", "fr"])
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--workers", type=int, default=CONCURRENCY)
    a = ap.parse_args()
    MAX_TOKENS = a.max_tokens
    CONCURRENCY = a.workers
    run(a.book, a.src_lang, a.resume)
