#!/usr/bin/env python3
"""Compatibility alias for build.py on the standalone branch."""
from build import main

if __name__ == "__main__":
    raise SystemExit(main())
