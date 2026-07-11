#!/usr/bin/env python3
# Backward-compat wrapper: delegating to scripts/run-ocr.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.argv[0] = os.path.join(os.path.dirname(__file__), "ocr_paddle.py")
exec(open(os.path.join(os.path.dirname(__file__), "..", "scripts", "run-ocr.py")).read())
