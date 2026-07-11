#!/usr/bin/env python3
# Backward-compat wrapper: delegating to scripts/run-scan.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.argv[0] = os.path.join(os.path.dirname(__file__), "scan_final.py")
exec(open(os.path.join(os.path.dirname(__file__), "..", "scripts", "run-scan.py")).read())
