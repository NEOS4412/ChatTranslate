#!/usr/bin/env python3
"""CLI: Split merged text into chapters."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.split import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--front", type=int, default=7, help="前 N 个章节视为前置")
    ap.add_argument("--protect", action="store_true", help="保留已存在的章节文件")
    a = ap.parse_args()
    run(a.book, a.front, a.protect)
