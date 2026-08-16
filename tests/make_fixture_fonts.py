#!/usr/bin/env python3
"""Generate a synthetic font workspace for smoke builds (CI, --inspect trials).

Creates a static Sans pair plus italic, a static Bengali face and a variable
Serif face — enough to exercise the TTC payload, optional-family fragments
and variable-axis config paths of a full build.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from synthfonts import build_synthetic_font

PLAN = (
    ("Sans/Regular.ttf", dict(family="Fixture Sans", style_name="Regular", us_weight_class=400)),
    ("Sans/Bold.ttf", dict(family="Fixture Sans", style_name="Bold", us_weight_class=700)),
    ("Sans/Italic.ttf", dict(family="Fixture Sans", style_name="Italic", us_weight_class=400, italic=True)),
    ("Bengali/Bengali-Regular.ttf", dict(family="Fixture Bengali", style_name="Regular", us_weight_class=400)),
    ("Serif/SerifVF-Roman.ttf", dict(family="Fixture Serif", style_name="Roman", us_weight_class=400, wght_axis=(100, 400, 900))),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="workspace directory to populate")
    args = parser.parse_args()
    for rel, kwargs in PLAN:
        path = args.output / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        build_synthetic_font(path, **kwargs)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
