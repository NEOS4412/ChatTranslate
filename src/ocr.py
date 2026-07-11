"""PaddleOCR 封装：PDF -> 按页 md + 图片，断点续传，页分隔符合并。

用法:
  export PADDLEOCR_TOKEN=...
  python3 bin/ocr_paddle.py books/_inbox/xxx.pdf books/<书名> --lang en
  python3 bin/ocr_paddle.py books/_inbox/xxx.pdf books/<书名> --resume
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"
POLL_INTERVAL = 5
MAX_RETRIES = 3


def post_job(pdf: Path, token: str) -> str:
    h = {"Authorization": f"bearer {token}"}
    data = {"model": MODEL, "optionalPayload": json.dumps({
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useChartRecognition": False,
    })}
    with pdf.open("rb") as f:
        r = requests.post(JOB_URL, headers=h, data=data, files={"file": f})
    r.raise_for_status()
    return r.json()["data"]["jobId"]


def poll(job_id: str, token: str) -> str:
    h = {"Authorization": f"bearer {token}"}
    while True:
        r = requests.get(f"{JOB_URL}/{job_id}", headers=h)
        r.raise_for_status()
        st = r.json()["data"]["state"]
        if st == "running":
            p = r.json()["data"].get("extractProgress", {})
            print(f"[poll] {p.get('extractedPages','?')}/{p.get('totalPages','?')}")
        elif st == "done":
            return r.json()["data"]["resultUrl"]["jsonUrl"]
        elif st == "failed":
            raise RuntimeError(r.json()["data"].get("errorMsg"))
        time.sleep(POLL_INTERVAL)


def save_pages(pages, ocr_dir: Path, img_dir: Path, skip: bool) -> int:
    n, saved = 0, 0
    for rec in pages:
        for res in rec["result"]["layoutParsingResults"]:
            md = ocr_dir / f"doc_{n}.md"
            if skip and md.exists() and md.stat().st_size > 0:
                n += 1; continue
            md.write_text(res["markdown"]["text"], encoding="utf-8")
            for p, url in res["markdown"]["images"].items():
                d = img_dir / p; d.parent.mkdir(parents=True, exist_ok=True)
                d.write_bytes(requests.get(url).content)
            for name, url in res["outputImages"].items():
                d = img_dir / f"{name}_{n}.jpg"
                if d.exists() and skip: continue
                d.write_bytes(requests.get(url).content)
            saved += 1; n += 1
    return saved


def merge(ocr_dir: Path, out: Path) -> None:
    files = sorted(ocr_dir.glob("doc_*.md"),
                   key=lambda p: int(re.search(r"\d+", p.stem).group()))
    parts = []
    for f in files:
        pn = int(re.search(r"\d+", f.stem).group())
        parts.append(f"<!-- page:{pn} -->\n\n{f.read_text(encoding='utf-8').rstrip()}\n")
    text = "\n".join(parts)
    # PaddleOCR 输出 <img src="imgs/...">, 合并文件位于 ocr/ 平级, 改为 images/imgs/
    text = text.replace('src="imgs/', 'src="images/imgs/')
    out.write_text(text, encoding="utf-8")
    print(f"[merge] {len(files)} pages -> {out}")


def run(pdf: Path, book: Path, resume: bool) -> None:
    tok = os.environ.get("PADDLEOCR_TOKEN")
    if not tok: sys.exit("ERROR: PADDLEOCR_TOKEN not set")
    ocr = book / "ocr"; imgs = ocr / "images"
    ocr.mkdir(parents=True, exist_ok=True); imgs.mkdir(parents=True, exist_ok=True)
    merged = ocr / "full_raw.md"

    if resume and list(ocr.glob("doc_*.md")):
        n = len(list(ocr.glob("doc_*.md"))); print(f"[resume] {n} pages, merge only")
        merge(ocr, merged); return

    print(f"[submit] {pdf.name}")
    jid = None
    for i in range(1, MAX_RETRIES + 1):
        try: jid = post_job(pdf, tok); break
        except Exception as e:
            print(f"[retry {i}/{MAX_RETRIES}] {e}")
            if i == MAX_RETRIES: raise
            time.sleep(5)
    url = poll(jid, tok)
    pages = [json.loads(l) for l in requests.get(url).text.splitlines() if l.strip()]
    (ocr / "_result.jsonl").write_text(
        "\n".join(json.dumps(p, ensure_ascii=False) for p in pages), encoding="utf-8")
    s = save_pages(pages, ocr, imgs, skip=resume)
    print(f"[save] {s} new pages")
    merge(ocr, merged)
