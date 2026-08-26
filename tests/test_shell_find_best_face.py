"""Runs the flash-time find_best_face heuristic against the shared vectors.

The function is extracted live from template/customize.sh by the harness
script, so any drift in the shell implementation shows up here immediately.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
VECTORS = json.loads((Path(__file__).parent / "weight_vectors.json").read_text(encoding="utf-8"))
CASES = VECTORS["shell_filename_cases"]


def _find_usable_bash() -> str | None:
    # On Windows, prefer Git Bash / MSYS bash over WSL system32 bash.exe
    for cand in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        shutil.which("bash"),
        shutil.which("sh"),
    ):
        if cand and Path(cand).is_file():
            if "system32" in str(cand).lower():
                continue
            return str(cand)
    found = shutil.which("bash")
    return found if found and "system32" not in str(found).lower() else None


USABLE_BASH = _find_usable_bash()


@pytest.mark.skipif(USABLE_BASH is None, reason="usable bash shell is not available")
def test_shell_find_best_face_vectors(tmp_path):
    bash = USABLE_BASH
    harness = Path(__file__).parent / "shell" / "run_find_best_face.sh"
    stdin = "".join(f"{case['weight']} {case['style']} {','.join(case['files'])}\n" for case in CASES)

    proc = subprocess.run(
        [bash, harness.as_posix(), (ROOT / "template" / "customize.sh").as_posix(), tmp_path.as_posix()],
        # Bytes input avoids newline translation to \r\n on Windows, which
        # would otherwise corrupt the last filename on every case line.
        input=stdin.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    assert proc.returncode == 0, f"harness failed:\n{stderr}"
    assert stderr.strip() == "", f"unexpected harness noise:\n{stderr}"

    results = {}
    for line in stdout.splitlines():
        number, _, name = line.partition(" ")
        results[int(number)] = None if name == "NONE" else name

    for index, case in enumerate(CASES, start=1):
        assert results.get(index) == case["expected"], (
            f"case {case['name']!r}: expected {case['expected']}, got {results.get(index)}"
        )
