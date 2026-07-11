#!/usr/bin/env bash
# 一键流水线: OCR -> 翻译 -> 清理 -> 校对 -> epub
# 用法: bin/build_book.sh books/<书名> <pdf_path> [--lang en|fr]
set -euo pipefail
usage() { echo "usage: $(basename "$0") <book_dir> <pdf_path> [--lang en|fr] [--resume]" >&2; exit 1; }
BOOK="${1:?$(usage)}"
PDF="${2:?$(usage)}"
LANG="en"
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang=*) LANG="${1#*=}"; shift;;
    --lang)   LANG="$2"; shift 2;;
    *) echo "unknown: $1" >&2; usage;;
  esac
done

export PADDLEOCR_TOKEN="${PADDLEOCR_TOKEN:-}"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"

echo "==> [0/5] Auto-extract cover from PDF"
COVER="$BOOK/cover.jpg"
if [[ ! -f "$COVER" ]] && command -v pdftoppm >/dev/null; then
  pdftoppm -f 1 -l 1 -r 150 -jpeg "$PDF" /tmp/_cov 2>/dev/null
  [[ -f /tmp/_cov-001.jpg ]] && mv /tmp/_cov-001.jpg "$COVER" && echo "  -> $COVER"
fi

echo "==> [1/5] OCR ($LANG)"
python3 scripts/run-ocr.py "$PDF" "$BOOK" --lang "$LANG" --resume

echo "==> [2/5] Translate"
python3 scripts/run-translate.py "$BOOK" --src-lang "$LANG" --resume

echo "==> [3/5] Clean + merge"
python3 scripts/run-clean.py "$BOOK" --titles --superscripts

echo "==> [4/5] Proofread"
python3 scripts/run-proofread.py "$BOOK"

echo "==> [5/5] Crowbook -> epub"
bash scripts/build-book.sh "$BOOK"
