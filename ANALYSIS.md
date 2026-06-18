# Source Repository Analysis

## Static template: MFFMv12

Strong parts retained:

- comprehensive static face model, including italic and condensed variants;
- collection-based packaging and explicit Android XML indices;
- robust font-name cleanup, dehinting, metadata work, Android metric repair, and legacy ZIP migration;
- optional Bengali, serif, monospace, and Google font-provider handling;
- signed ZIP verification.

Constraints addressed in the MFFMv14 template:

- static logic was embedded in a large builder and generated shell block;
- signing logic was duplicated inside `build.py`;
- the installer only understood indexed collection faces;
- the old updater needed a separate implementation of face detection.

## Variable template: MFFMv13

Strong parts retained:

- `fvar`-aware axis discovery and default-axis preservation;
- separate upright/italic variable payload support;
- Magisk, KernelSU, and APatch packaging plus OverlayFS handling;
- installation logging and post-mount/uninstall lifecycle scripts;
- reusable external ZipSignerust helper;
- optional resource behavior.

Constraints addressed and intentional conventions clarified in the MFFMv14 template:

- it assumed variable fonts and could not compile a static family;
- builder and updater duplicated axis/config generation;
- `DroidSans-Bold.ttf` was used as an italic filename; this is intentionally retained as an Android compatibility/spoofing convention, while the generated XML still identifies the face as italic;
- the installer parsed axes at install time and used Bash-only `[[ ... ]]` in a `/system/bin/sh` script;
- several large XML patch paths overlapped, increasing maintenance and regression risk.

## MFFMv14 architecture

The new template has one source of truth:

- `font_module.py` performs discovery, model detection, processing, compilation, XML rendering, and metadata updates;
- `build.py` packages a new module;
- `update.py` extracts old modules and calls the same compiler core;
- `zipsigner_auto.py` owns signing setup and verification;
- `customize.sh` consumes generated files and remains agnostic to font internals.

The key design decision is to move all font intelligence to the desktop compiler. Android receives deterministic XML fragments and a small `FONT_MODE` contract. Multi-face static families use TTC indices while retaining the intentional `DroidSans.ttf` external name; single-face static builds use a normal standalone TTF. Variable faces use actual axis tags and values. The installer follows the same patch path for both.
