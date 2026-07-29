#!/usr/bin/env python3
"""Compile static or variable fonts into an unsigned flashable MFFM module."""

from __future__ import annotations

import sys
from pathlib import Path

from build import build_module, parse_args

ROOT = Path(__file__).resolve().parent


def main() -> int:
    sys.argv.append("--no-sign")
    args = parse_args()
    if not (ROOT / "customize.sh").exists():
        raise SystemExit("Template payload is incomplete: customize.sh is missing")
    build_module(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
