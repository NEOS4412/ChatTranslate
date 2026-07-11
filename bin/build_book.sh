#!/usr/bin/env bash
# 一键流水线: OCR -> 翻译 -> 清理 -> 校对 -> epub
# 用法: bin/build_book.sh books/<书名> <pdf_path> [--lang en|fr]
set -euo pipefail
BOOK="${1:?usage: build_book.sh books/<书名> <pdf_path> [--lang en|fr]}"
PDF="${2:?missing pdf path}"
LANG="en"
[[ "${3:-}" == "--lang=fr" ]] && LANG="fr"

export PADDLEOCR_TOKEN="${PADDLEOCR_TOKEN:-}"
export DEEPSEEK_API_KEY="${DEEPSEEK_API_KEY:-}"

echo "==> [0/5] Auto-extract cover from PDF"
COVER="$BOOK/cover.jpg"
if [[ ! -f "$COVER" ]] && command -v pdftoppm >/dev/null; then
  pdftoppm -f 1 -l 1 -r 150 -jpeg "$PDF" /tmp/_cov 2>/dev/null
  [[ -f /tmp/_cov-001.jpg ]] && mv /tmp/_cov-001.jpg "$COVER" && echo "  -> $COVER"
fi

echo "==> [1/5] OCR ($LANG)"
python3 bin/ocr_paddle.py "$PDF" "$BOOK" --lang "$LANG" --resume

echo "==> [2/5] Translate"
python3 bin/translate.py "$BOOK" --src-lang "$LANG" --resume

echo "==> [3/5] Clean + merge"
python3 bin/clean_md.py "$BOOK" --titles --superscripts

echo "==> [4/5] Proofread"
python3 bin/proofread.py "$BOOK"

echo "==> [5/5] Crowbook -> epub"
bash bin/crowbook_build.sh "$BOOK"
