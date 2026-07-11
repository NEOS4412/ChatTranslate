#!/usr/bin/env bash
# crowbook 构建 epub
# 用法:
#   方案 A: bin/crowbook_build.sh books/<书名>             # 单文件 + inline YAML
#   方案 B: bin/crowbook_build.sh books/<书名>/<书名>.book # 拆分章节
set -euo pipefail

# 工作目录：项目根（脚本所在目录的上级）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

INPUT="${1:?usage: crowbook_build.sh books/<书名> 或 books/<书名>/<书名>.book}"

command -v crowbook >/dev/null || { echo "ERROR: crowbook not installed" >&2; exit 1; }

if [[ "$INPUT" == *.book ]]; then
  # 方案 B
  [[ -f "$INPUT" ]] || { echo "ERROR: $INPUT not found" >&2; exit 1; }
  echo "[crowbook B] cfg=$INPUT"
  crowbook "$INPUT"
else
  # 方案 A
  BOOK_DIR="$INPUT"
  PROOF_ABS="$BOOK_DIR/proofread/full_zh.md"
  [[ -f "$PROOF_ABS" ]] || { echo "ERROR: $PROOF_ABS missing" >&2; exit 1; }

  DIR_NAME="$(basename "$BOOK_DIR")"
  if [[ "$DIR_NAME" == *_* ]]; then
    TITLE="${DIR_NAME%_*}"; AUTHOR="${DIR_NAME#*_}"
  else
    TITLE="$DIR_NAME"; AUTHOR="未知"
  fi

  GLOBAL_OUT="$PROJECT_ROOT/output"
  mkdir -p "$GLOBAL_OUT"
  SAFE_TITLE="$(echo "$TITLE" | tr '/\\:*?"<>|' '_')"
  EPUB_ABS="$GLOBAL_OUT/${SAFE_TITLE}.epub"

  if [[ -f "$BOOK_DIR/cover.jpg" ]]; then
    COVER_ABS="$PROJECT_ROOT/$BOOK_DIR/cover.jpg"
  else
    COVER_ABS=""
  fi

  TMP="$(mktemp -t crowbook_XXXXXX).md"
  {
    echo "---"
    echo "author: $AUTHOR"
    echo "title: $TITLE"
    echo "lang: zh-CN"
    echo "output: [epub]"
    echo "epub.version: 3"
    echo "resources.base_path: $PROJECT_ROOT/$BOOK_DIR"
    if [[ -n "$COVER_ABS" ]]; then
      echo "cover: $COVER_ABS"
    fi
    echo "---"
    echo
    cat "$PROOF_ABS"
  } > "$TMP"

  echo "[crowbook A] book=$BOOK_DIR"
  echo "[crowbook A] cover=${COVER_ABS:-<none>}"
  echo "[crowbook A] out=$EPUB_ABS"
  crowbook -s "$TMP" --set output.epub "$EPUB_ABS"
  rm -f "$TMP"
  echo "[done] $EPUB_ABS"
fi
