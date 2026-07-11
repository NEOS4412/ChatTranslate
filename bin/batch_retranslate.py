"""批量重新翻译 OCR 中翻译不合格的页面。

检测标准：中文占比 < 80% 的 translated 页面，重新调用 DeepSeek 翻译。
还支持清理已有翻译中的 <!-- page:N --> 残留。
DeepSeek 模型: deepseek-v4-flash, max_tokens=8000, reasoning_effort=low
"""
from __future__ import annotations
import json, os, re, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

API_URL = "https://api.deepseek.com/v1/chat/completions"
MODEL = "deepseek-v4-flash"
MAX_RETRIES = 3
CONCURRENCY = 5  # 降低并发避免 API 限制
MAX_TOKENS = 8000

SYSTEM_PROMPT = """你是一名专业的文学翻译，负责将原文（法语或英语）的 markdown 内容翻译成简体中文。

【严格规则】
1. 只翻译正文。
2. 保留所有 markdown 格式标记。
3. 保留段落结构。
4. 专业术语和专有名词请参考术语表（如果有提供）。
5. 不要添加任何解释性文字。
6. 输出严格 markdown，不加 ``` 围栏。
7. 尽可能将全文完整翻译，不要省略任何内容。"""

USER_TEMPLATE = """原文语言：{src_lang}

术语表：
{glossary}

请将以下内容完整翻译成简体中文：

{source}"""

def call_llm(messages: list, key: str) -> str:
    """调用 DeepSeek API，带重试机制"""
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


def get_ocr_page(book_dir: Path, page_num: int) -> str | None:
    """从 raw OCR 文件中读取指定页的原文"""
    # 方案1: full_raw.md
    raw = book_dir / "ocr" / "full_raw.md"
    if raw.exists():
        text = raw.read_text(encoding="utf-8")
        # 找 <!-- page:N --> 之间的内容
        pattern = rf"<!-- page:{page_num} -->\s*(.*?)(?=<!-- page:\d+ -->|\Z)"
        m = re.search(pattern, text, re.S)
        if m:
            return m.group(1).strip()
    # 方案2: 按页 OCR 文件
    page_file = book_dir / "ocr" / f"doc_{page_num}.md"
    if page_file.exists():
        return page_file.read_text(encoding="utf-8").strip()
    return None


def chinese_ratio(text: str) -> float:
    """计算中文字符占比"""
    cn = len(re.findall(r'[\u4e00-\u9fff]', text))
    total = len(text.strip())
    return cn / total if total > 0 else 0


def load_glossary(book_dir: Path) -> str:
    """加载术语表"""
    glossary_file = book_dir / "translated" / "_glossary.json"
    if glossary_file.exists():
        gloss = json.loads(glossary_file.read_text(encoding="utf-8"))
        return "\n".join(f"{k} -> {v}" for k, v in gloss.items())
    return "（暂无）"


def scan_and_retranslate(book_dir: Path, src_lang: str, threshold: float = 0.5, dry_run: bool = False) -> list:
    """扫描 translated/ 目录，重新翻译低质量页面"""
    trans_dir = book_dir / "translated"
    if not trans_dir.exists():
        print(f"ERROR: {trans_dir} not found")
        return []

    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not set")
        return []

    glossary_str = load_glossary(book_dir)
    # 加载已有术语表为 dict
    glossary_file = book_dir / "translated" / "_glossary.json"
    glossary = {}
    if glossary_file.exists():
        glossary = json.loads(glossary_file.read_text(encoding="utf-8"))

    # 扫描所有翻译页面
    pages_to_fix = []
    for f in sorted(os.listdir(trans_dir), key=lambda x: int(re.search(r'\d+', x).group()) if re.search(r'\d+', x) else 0):
        if not f.endswith('.md') or f.startswith('_'):
            continue
        text = (trans_dir / f).read_text(encoding="utf-8")
        # 去除 <!-- page:N --> 行后检查中文比例
        text_no_header = re.sub(r'<!-- page:\d+ -->\s*', '', text).strip()
        if not text_no_header:
            continue
        ratio = chinese_ratio(text_no_header)
        if ratio < threshold and len(text_no_header) > 100:
            page_num = int(re.search(r'\d+', f).group())
            pages_to_fix.append((page_num, f, len(text_no_header), ratio))

    print(f"\n🔍 扫描完成：发现 {len(pages_to_fix)} 个需要重新翻译的页面（中文占比 < {threshold:.0%}）")
    for pn, fn, size, ratio in pages_to_fix:
        print(f"  {fn}: {size} chars, 中文 {ratio:.1%}")

    if dry_run or not pages_to_fix:
        return pages_to_fix

    # 重新翻译
    def retranslate_one(page_num: int, filename: str) -> tuple[str, str, bool]:
        ocr_text = get_ocr_page(book_dir, page_num)
        if not ocr_text:
            print(f"  ⚠ {filename}: 找不到 OCR 原文，跳过")
            return filename, "", False

        # 去除 OCR 原文中已有的 <!-- page:N --> 标记
        clean_ocr = re.sub(r'<!-- page:\d+ -->\s*', '', ocr_text).strip()

        # 构建术语表提示
        # 尝试在原文中匹配术语
        matched_terms = {}
        for term, trans in glossary.items():
            if term.lower() in clean_ocr.lower():
                matched_terms[term] = trans

        gloss_str = "\n".join(f"{k} -> {v}" for k, v in matched_terms.items()) if matched_terms else "（暂无）"

        msgs = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                src_lang=src_lang, glossary=gloss_str, source=clean_ocr)},
        ]

        try:
            result = call_llm(msgs, key)
            header = f"<!-- page:{page_num} -->\n\n"
            (trans_dir / filename).write_text(header + result.strip(), encoding="utf-8")
            new_ratio = chinese_ratio(result)
            print(f"  ✅ {filename}: 重新翻译完成，中文占比 {new_ratio:.1%}")
            return filename, result, True
        except Exception as e:
            print(f"  ❌ {filename}: 翻译失败 - {e}")
            return filename, "", False

    print(f"\n🚀 开始重新翻译（并发 {CONCURRENCY}）...")
    success = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(retranslate_one, pn, fn): (pn, fn) for pn, fn, _, _ in pages_to_fix}
        for future in as_completed(futures):
            fn, _, ok = future.result()
            if ok:
                success += 1

    print(f"\n📊 完成：{success}/{len(pages_to_fix)} 页重新翻译成功")
    return pages_to_fix


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量重翻低质量翻译页")
    parser.add_argument("book", type=Path, help="书籍目录路径")
    parser.add_argument("--src-lang", choices=["en", "fr"], default="fr", help="原文语言")
    parser.add_argument("--threshold", type=float, default=0.5, help="中文占比阈值，低于此值重新翻译")
    parser.add_argument("--dry-run", action="store_true", help="仅扫描不翻译")
    parser.add_argument("--workers", type=int, default=CONCURRENCY, help="并发数")
    args = parser.parse_args()

    CONCURRENCY = args.workers
    scan_and_retranslate(args.book, args.src_lang, args.threshold, args.dry_run)
