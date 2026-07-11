#!/usr/bin/env python3
"""CLI entry point. Delegates to src.merge."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
from pathlib import Path

from src.merge import *

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("book", type=Path)
    ap.add_argument("--src-lang", choices=["en", "fr", "auto"], default="fr")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()
