#!/usr/bin/env python3
"""Build script for MFFM Font Builder Android APK.

Cross-platform: Works on Linux (GitHub Actions ubuntu-latest), macOS, and Windows.
Compiles Android resources, links with aapt2, compiles Java classes,
translates to dex with d8, packages unaligned APK, zipaligns and signs with apksigner.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_DIR = ROOT / "app-project"
BUILD_DIR = PROJECT_DIR / "build"
DIST_DIR = ROOT / "dist"

def find_jdk() -> tuple[Path, Path, Path]:
    java_home = os.environ.get("JAVA_HOME")
    javac_name = "javac.exe" if sys.platform == "win32" else "javac"
    keytool_name = "keytool.exe" if sys.platform == "win32" else "keytool"

    if java_home:
        jdk = Path(java_home)
        if (jdk / "bin" / javac_name).exists():
            return jdk, jdk / "bin" / javac_name, jdk / "bin" / keytool_name

    which_javac = shutil.which("javac")
    if which_javac:
        javac = Path(which_javac).resolve()
        jdk = javac.parent.parent
        keytool = javac.parent / keytool_name
        if not keytool.exists():
            which_keytool = shutil.which("keytool")
            keytool = Path(which_keytool).resolve() if which_keytool else javac.parent / keytool_name
        return jdk, javac, keytool

    for p in [Path("C:/Program Files/Microsoft"), Path("C:/Program Files/Eclipse Adoptium"), Path("C:/Program Files/Java")]:
        if p.exists():
            for child in sorted(p.iterdir(), reverse=True):
                if (child / "bin" / javac_name).exists():
                    return child, child / "bin" / javac_name, child / "bin" / keytool_name

    raise SystemExit("JDK 17+ not found. Please set JAVA_HOME or ensure javac and keytool are in PATH.")

def find_android_sdk() -> tuple[Path, Path, Path, Path, Path, Path]:
    candidates = []
    for env_var in ["ANDROID_HOME", "ANDROID_SDK_ROOT"]:
        val = os.environ.get(env_var)
        if val and Path(val).is_dir():
            candidates.append(Path(val))

    if sys.platform == "win32":
        candidates.extend([
            Path("C:/android-sdk"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
        ])
    else:
        candidates.extend([
            Path("/usr/local/lib/android/sdk"),
            Path(os.environ.get("HOME", "")) / "Android" / "Sdk"
        ])

    sdk_dir = None
    for c in candidates:
        if c.exists() and (c / "build-tools").exists():
            sdk_dir = c
            break

    if not sdk_dir:
        # Check if Android 14 dir was extracted directly into c:/android-sdk
        if Path("C:/android-sdk/android-14").exists():
            sdk_dir = Path("C:/android-sdk")

    if not sdk_dir:
        raise SystemExit(f"Android SDK not found in candidates: {[str(c) for c in candidates]}. Please set ANDROID_HOME.")

    # Find build-tools
    bt_dir = sdk_dir / "build-tools"
    build_tools_dir = None
    if bt_dir.exists():
        versions = sorted(bt_dir.iterdir(), reverse=True)
        if versions:
            build_tools_dir = versions[0]
    elif (sdk_dir / "android-14").exists():
        build_tools_dir = sdk_dir / "android-14"

    if not build_tools_dir or not build_tools_dir.exists():
        raise SystemExit(f"Could not find build-tools in {sdk_dir}")

    # Find android.jar
    platforms_dir = sdk_dir / "platforms"
    platform_jar = None
    if platforms_dir.exists():
        for p in sorted(platforms_dir.iterdir(), reverse=True):
            candidate_jar = p / "android.jar"
            if candidate_jar.exists():
                platform_jar = candidate_jar
                break
    elif (sdk_dir / "android-34" / "android.jar").exists():
        platform_jar = sdk_dir / "android-34" / "android.jar"

    if not platform_jar or not platform_jar.exists():
        raise SystemExit(f"Could not find android.jar in {sdk_dir}/platforms")

    exe_suffix = ".exe" if sys.platform == "win32" else ""
    bat_suffix = ".bat" if sys.platform == "win32" else ""

    aapt2 = build_tools_dir / f"aapt2{exe_suffix}"
    d8 = build_tools_dir / f"d8{bat_suffix}"
    zipalign = build_tools_dir / f"zipalign{exe_suffix}"
    apksigner = build_tools_dir / f"apksigner{bat_suffix}"

    return sdk_dir, build_tools_dir, platform_jar, aapt2, d8, zipalign, apksigner

def run_cmd(cmd: list[str | Path], env: dict[str, str] | None = None) -> None:
    print(f"  [exec] {' '.join(str(c) for c in cmd[:5])}...")
    res = subprocess.run([str(c) for c in cmd], env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error executing command: {res.stderr.strip() or res.stdout.strip()}")
        sys.exit(res.returncode)

def prepare_apk_payloads() -> None:
    """Ensure libmffm_python.so and engine.zip are generated from runtime tarballs."""
    assets_dir = PROJECT_DIR / "src" / "main" / "assets"
    jni_arm64 = PROJECT_DIR / "src" / "main" / "jniLibs" / "arm64-v8a"
    jni_x64 = PROJECT_DIR / "src" / "main" / "jniLibs" / "x86_64"
    engine_zip = assets_dir / "engine.zip"

    arm64_so = jni_arm64 / "libmffm_python.so"
    x64_so = jni_x64 / "libmffm_python.so"

    if arm64_so.exists() and x64_so.exists() and engine_zip.exists():
        print("  [cached] APK payloads and native libraries already present.")
        return

    print("  [payload] Preparing APK native libraries and bundled engine assets...")
    jni_arm64.mkdir(parents=True, exist_ok=True)
    jni_x64.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    runtime_arm64 = ROOT / "runtime-template" / "runtime" / "aarch64" / "python.tar.xz"
    runtime_x64 = ROOT / "runtime-template" / "runtime" / "x64" / "python.tar.xz"

    if not runtime_arm64.exists() or not runtime_x64.exists():
        print("  [payload] Runtime tarballs not found. Running prepare_runtime.py...")
        subprocess.check_call([sys.executable, str(ROOT / "prepare_runtime.py"), "--abi", "aarch64", "--abi", "x64", "--no-strip"])

    # Extract python binaries
    if not arm64_so.exists():
        with tarfile.open(runtime_arm64, "r:xz") as tar:
            f = tar.extractfile("./bin/python3")
            arm64_so.write_bytes(f.read())
        print("  [payload] Extracted arm64 libmffm_python.so")

    if not x64_so.exists():
        with tarfile.open(runtime_x64, "r:xz") as tar:
            f = tar.extractfile("./bin/python3")
            x64_so.write_bytes(f.read())
        print("  [payload] Extracted x64 libmffm_python.so")

    # Build engine.zip
    temp_engine = BUILD_DIR / "temp_engine"
    if temp_engine.exists():
        shutil.rmtree(temp_engine)
    temp_engine.mkdir(parents=True, exist_ok=True)

    print("  [payload] Extracting standard library and site-packages...")
    with tarfile.open(runtime_arm64, "r:xz") as tar:
        for m in tar.getmembers():
            if m.name.startswith("./lib/"):
                tar.extract(m, temp_engine)

    lib_dir = temp_engine / "lib" / "python3.11"
    sp_dir = lib_dir / "site-packages"
    sp_dir.mkdir(parents=True, exist_ok=True)

    # Add opentype-feature-freezer
    wheel_url = "https://files.pythonhosted.org/packages/66/5e/e46320d3c2df59c98a41b3c1f2a1bf2fb1ee1b67dbed8a9201416a3b5777/opentype_feature_freezer-1.32.2-py3-none-any.whl"
    print("  [payload] Fetching opentype-feature-freezer wheel...")
    req = urllib.request.Request(wheel_url, headers={"User-Agent": "MFFMv14-builder"})
    with urllib.request.urlopen(req) as resp:
        wheel_bytes = resp.read()
    with zipfile.ZipFile(io.BytesIO(wheel_bytes)) as z:
        z.extractall(sp_dir)

    # Copy scripts
    scripts_dir = temp_engine / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for s in ["build_standalone.py", "font_module_standalone.py", "runtime_helper.py", "zipsigner_auto.py"]:
        shutil.copy2(ROOT / s, scripts_dir / s)

    # Copy template-standalone
    shutil.copytree(ROOT / "template-standalone", scripts_dir / "template-standalone", dirs_exist_ok=True)

    # Copy or download zipsignerust arm64 binary
    signer_bin_dir = scripts_dir / ".mffm-signer" / "bin"
    signer_bin_dir.mkdir(parents=True, exist_ok=True)
    local_signer = ROOT / ".mffm-signer" / "bin" / "zipsignerust-android-arm64"
    target_signer = signer_bin_dir / "zipsignerust-android-arm64"
    if local_signer.exists():
        shutil.copy2(local_signer, target_signer)
    else:
        signer_url = "https://github.com/MrCarb0n/zipsignerust/releases/download/latest/zipsignerust-android-arm64"
        print("  [payload] Downloading zipsignerust-android-arm64...")
        req = urllib.request.Request(signer_url, headers={"User-Agent": "MFFMv14-builder"})
        with urllib.request.urlopen(req) as resp, target_signer.open("wb") as out:
            out.write(resp.read())

    print("  [payload] Packaging engine.zip...")
    with zipfile.ZipFile(engine_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
        for root, dirs, files in os.walk(temp_engine):
            for file in files:
                full = Path(root) / file
                rel = full.relative_to(temp_engine)
                zout.write(full, rel.as_posix())

    shutil.rmtree(temp_engine, ignore_errors=True)
    print(f"  [payload] engine.zip created ({engine_zip.stat().st_size // (1024*1024)} MB).")

def update_manifest_version(version: str, version_code: int) -> None:
    manifest_path = PROJECT_DIR / "src" / "main" / "AndroidManifest.xml"
    content = manifest_path.read_text(encoding="utf-8")
    content = re.sub(r'android:versionCode="[0-9]+"', f'android:versionCode="{version_code}"', content)
    content = re.sub(r'android:versionName="[^"]+"', f'android:versionName="{version}"', content)
    manifest_path.write_text(content, encoding="utf-8")

def main():
    parser = argparse.ArgumentParser(description="Compile and package MFFM Font Builder Android APK")
    parser.add_argument("--version", default="14.0.0", help="version string for APK (default: 14.0.0)")
    parser.add_argument("--version-code", type=int, default=1400, help="numeric versionCode for APK (default: 1400)")
    parser.add_argument("--output-dir", type=Path, default=DIST_DIR, help="directory to store final APK (default: ./dist)")
    args = parser.parse_args()

    print("=" * 64)
    print("  MFFM Font Builder — Android APK Compiler")
    print("=" * 64)
    print(f"  Target Version  : {args.version} (versionCode: {args.version_code})")
    print(f"  Output Directory: {args.output_dir}")

    jdk, javac, keytool = find_jdk()
    print(f"  JDK Path        : {jdk}")

    sdk_dir, build_tools_dir, platform_jar, aapt2, d8, zipalign, apksigner = find_android_sdk()
    print(f"  Android SDK     : {sdk_dir}")
    print(f"  Build Tools     : {build_tools_dir}")
    print(f"  Platform JAR    : {platform_jar}")
    print("-" * 64)

    env = os.environ.copy()
    env["JAVA_HOME"] = str(jdk)
    env["PATH"] = f"{jdk / 'bin'}{os.pathsep}{build_tools_dir}{os.pathsep}{env.get('PATH', '')}"

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gen_dir = BUILD_DIR / "gen"
    obj_dir = BUILD_DIR / "obj"
    dex_dir = BUILD_DIR / "dex"
    for d in [gen_dir, obj_dir, dex_dir]:
        d.mkdir(parents=True, exist_ok=True)

    update_manifest_version(args.version, args.version_code)

    # 1. Payloads
    prepare_apk_payloads()

    # 2. Compile resources
    print("1. Compiling Android resources with aapt2...")
    compiled_res = BUILD_DIR / "compiled_res.zip"
    run_cmd([aapt2, "compile", "--dir", PROJECT_DIR / "src" / "main" / "res", "-o", compiled_res], env)

    # 3. Link resources & generate R.java
    print("2. Linking resources and generating R.java...")
    base_apk = BUILD_DIR / "base.apk"
    run_cmd([
        aapt2, "link",
        "-o", base_apk,
        "-I", platform_jar,
        "--manifest", PROJECT_DIR / "src" / "main" / "AndroidManifest.xml",
        "--java", gen_dir,
        compiled_res,
        "--auto-add-overlay"
    ], env)

    # 4. Compile Java classes
    print("3. Compiling Java sources with javac...")
    java_files = list(gen_dir.rglob("*.java")) + list((PROJECT_DIR / "src" / "main" / "java").rglob("*.java"))
    run_cmd([javac, "-cp", platform_jar, "-d", obj_dir] + java_files, env)

    # 5. Dex classes with d8
    print("4. Converting class files to dex with d8...")
    class_files = list(obj_dir.rglob("*.class"))
    run_cmd([d8, "--lib", platform_jar, "--output", dex_dir] + class_files, env)

    # 6. Assemble unaligned APK
    print("5. Assembling unaligned APK package...")
    unaligned_apk = BUILD_DIR / "unaligned.apk"
    if unaligned_apk.exists():
        unaligned_apk.unlink()

    assets_dir = PROJECT_DIR / "src" / "main" / "assets"
    jni_dir = PROJECT_DIR / "src" / "main" / "jniLibs"
    dex_file = dex_dir / "classes.dex"

    with zipfile.ZipFile(base_apk, "r") as zin, zipfile.ZipFile(unaligned_apk, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.write(dex_file, "classes.dex", compress_type=zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                full = Path(root) / file
                rel = "assets/" + full.relative_to(assets_dir).as_posix()
                zout.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)
        for root, dirs, files in os.walk(jni_dir):
            for file in files:
                full = Path(root) / file
                rel = "lib/" + full.relative_to(jni_dir).as_posix()
                zout.write(full, rel, compress_type=zipfile.ZIP_STORED)

    # 7. Zipalign
    print("6. Page-aligning APK with zipalign...")
    aligned_apk = BUILD_DIR / "aligned.apk"
    if aligned_apk.exists():
        aligned_apk.unlink()
    run_cmd([zipalign, "-p", "-f", "4", unaligned_apk, aligned_apk], env)

    # 8. Keystore & Sign
    print("7. Signing APK with apksigner...")
    keystore = BUILD_DIR / "debug.keystore"
    if not keystore.exists():
        run_cmd([
            keytool, "-genkey", "-v",
            "-keystore", keystore,
            "-storepass", "android",
            "-alias", "androiddebugkey",
            "-keypass", "android",
            "-keyalg", "RSA",
            "-keysize", "2048",
            "-validity", "10000",
            "-dname", "CN=MFFM,O=Mistu,C=US"
        ], env)

    output_apk = args.output_dir / f"MFFM-Font-Module-Builder-v{args.version}.apk"
    if output_apk.exists():
        output_apk.unlink()
    run_cmd([
        apksigner, "sign",
        "--ks", keystore,
        "--ks-pass", "pass:android",
        "--ks-key-alias", "androiddebugkey",
        "--key-pass", "pass:android",
        "--out", output_apk,
        aligned_apk
    ], env)

    # 9. Verify
    print("8. Verifying APK signature...")
    run_cmd([apksigner, "verify", "--verbose", output_apk], env)

    size_mb = output_apk.stat().st_size / (1024 * 1024)
    print("=" * 64)
    print(f"  SUCCESS! APK built at: {output_apk}")
    print(f"  Package Size: {size_mb:.2f} MB")
    print("=" * 64)

if __name__ == "__main__":
    main()
