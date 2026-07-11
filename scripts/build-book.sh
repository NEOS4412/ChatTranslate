#!/usr/bin/env bash
# 一键流水线: OCR → 翻译 → 清理 → 切分章节 → 段合并 → 校对 → 扫描门禁 → EPUB → 验证
# 用法: scripts/build-book.sh books/<书名> <pdf_path> [--lang en|fr] [--resume]
#
# 依赖: yt-ocr / yt-translate / yt-clean / yt-split / yt-merge
#       yt-proofread / yt-scan / yt-epub / yt-verify-epub
# 安装: pip install -e .
#
# 目录约定（详见 README）:
#   ocr/                  OCR 产出（可删除重建）
#   translated/chapters/  逐章翻译原文
#   proofread/full_zh.md  合并+清理后的中文全文
#   final/ch_NNN.md       按二级标题切好的章节
#   output/<书名>.epub    最终交付物
set -euo pipefail

usage() { echo "usage: $(basename "$0") <book_dir> <pdf_path> [--lang en|fr] [--resume]" >&2; exit 1; }
[[ $# -ge 2 ]] || usage

BOOK="${1:?$(usage)}"
PDF="${2:?$(usage)}"
LANG="en"
RESUME=0
shift 2
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lang=*) LANG="${1#*=}"; shift;;
    --lang)   LANG="$2"; shift 2;;
    --resume) RESUME=1; shift;;
    *) echo "unknown: $1" >&2; usage;;
  esac
done

: "${PADDLEOCR_TOKEN:?PADDLEOCR_TOKEN required}"
: "${DEEPSEEK_API_KEY:?DEEPSEEK_API_KEY required}"

# ── [0] 提取封面（mktemp 避免并发碰撞 /tmp）──
echo "==> [0/7] Auto-extract cover"
COVER="$BOOK/cover.jpg"
if [[ ! -f "$COVER" ]] && command -v pdftoppm >/dev/null; then
  TMP_PREFIX="$(mktemp -t yishu_cov_XXXXXX)"
  if pdftoppm -f 1 -l 1 -r 150 -jpeg "$PDF" "$TMP_PREFIX" 2>/dev/null; then
    [[ -f "${TMP_PREFIX}-001.jpg" ]] && mv "${TMP_PREFIX}-001.jpg" "$COVER" && echo "  -> $COVER"
  fi
  rm -f "${TMP_PREFIX}"*.jpg 2>/dev/null || true
fi

echo "==> [1/7] OCR ($LANG)"
if [[ "$RESUME" -eq 1 ]]; then yt-ocr      "$PDF" "$BOOK" --lang "$LANG" --resume
else                              yt-ocr      "$PDF" "$BOOK" --lang "$LANG"
fi

echo "==> [2/7] Translate"
if [[ "$RESUME" -eq 1 ]]; then yt-translate "$BOOK" --src-lang "$LANG" --resume
else                              yt-translate "$BOOK" --src-lang "$LANG"
fi

echo "==> [3/7] Clean (merge chapters + LaTeX/footnotes/titles)"
yt-clean "$BOOK" --titles --superscripts

echo "==> [4/7] Split chapters"
yt-split "$BOOK" --front 8 --protect

echo "==> [5/7] Merge broken paragraphs (final/)"
yt-merge "$BOOK"

echo "==> [6/7] Proofread"
yt-proofread "$BOOK"

echo "==> [7/7] Quality gate + EPUB build"
yt-scan  "$BOOK" --src-lang "$LANG" --workers 10 --fail-on error
yt-epub  "$BOOK"
yt-verify-epub "$BOOK"

echo "✅ 一键流水线完成: $BOOK"
