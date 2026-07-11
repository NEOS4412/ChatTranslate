#!/usr/bin/env python3
"""CLI: Clean translated markdown."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.clean import run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--titles", action="store_true", help="批量降一级章节标题")
    ap.add_argument("--superscripts", action="store_true", help="孤立上标补空格")
    a = ap.parse_args()
    run(a.book, a.titles, a.superscripts)
