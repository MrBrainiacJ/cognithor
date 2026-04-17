"""Build Cognithor Windows Installer.

Creates an Inno Setup installer with:
  - Embedded Python 3.12 + cognithor[all] dependencies
  - Ollama binary
  - Flutter Command Center web build
  - Launcher script

Usage:
    python installer/build_installer.py

Prerequisites:
    - Inno Setup 6+ installed (iscc.exe in PATH or default location)
    - Internet connection (downloads Python, Ollama)
    - pip install hatchling (to build cognithor wheel)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# --- Config ---
PYTHON_VERSION = "3.12.9"
PYTHON_EMBED_URL = (
    f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
)
OLLAMA_URL = "https://github.com/ollama/ollama/releases/latest/download/ollama-windows-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = PROJECT_ROOT / "installer" / "build"
DIST_DIR = PROJECT_ROOT / "installer" / "dist"

COGNITHOR_VERSION = None  # read from pyproject.toml


def read_version() -> str:
    """Read version from pyproject.toml."""
    toml = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    for line in toml.splitlines():
        if line.strip().startswith("version"):
            return line.split("=")[1].strip().strip('"')
    raise RuntimeError("Could not read version from pyproject.toml")


def download(url: str, dest: Path, desc: str = "") -> None:
    """Download a file with progress."""
    print(f"  Downloading {desc or url}...")
    if dest.exists():
        print(f"  [SKIP] Already exists: {dest.name}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, dest)
    print(f"  [OK] {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")


def step_python_embed() -> Path:
    """Step 1: Create embedded Python with cognithor installed."""
    print("\n=== Step 1: Embedded Python ===")

    python_dir = BUILD_DIR / "python"
    if python_dir.exists():
        print("  [SKIP] python/ already built")
        return python_dir

    # Download embedded Python
    zip_path = BUILD_DIR / "downloads" / f"python-{PYTHON_VERSION}-embed.zip"
    download(PYTHON_EMBED_URL, zip_path, f"Python {PYTHON_VERSION} Embeddable")

    # Extract
    python_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(python_dir)

    # Enable site-packages: uncomment "import site" in python312._pth
    pth_files = list(python_dir.glob("python*._pth"))
    for pth in pth_files:
        content = pth.read_text()
        content = content.replace("#import site", "import site")
        pth.write_text(content)
        print(f"  [OK] Enabled site-packages in {pth.name}")

    # Install pip
    get_pip = BUILD_DIR / "downloads" / "get-pip.py"
    download(GET_PIP_URL, get_pip, "get-pip.py")

    python_exe = python_dir / "python.exe"
    subprocess.run(
        [str(python_exe), str(get_pip), "--no-warn-script-location"],
        check=True,
        cwd=str(python_dir),
    )
    print("  [OK] pip installed")

    # Install setuptools (needed by some dependencies)
    subprocess.run(
        [
            str(python_exe),
            "-m",
            "pip",
            "install",
            "setuptools",
            "wheel",
            "--no-warn-script-location",
        ],
        check=True,
    )
    print("  [OK] setuptools installed")

    # Build cognithor wheel
    print("  Building cognithor wheel...")
    wheel_dir = BUILD_DIR / "wheel"
    wheel_dir.mkdir(exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(PROJECT_ROOT),
            "--wheel-dir",
            str(wheel_dir),
            "--no-deps",
        ],
        check=True,
    )

    # Install cognithor[all] into embedded Python
    print("  Installing cognithor[all] into embedded Python...")
    wheels = list(wheel_dir.glob("cognithor-*.whl"))
    if not wheels:
        raise RuntimeError("No cognithor wheel found")

    subprocess.run(
        [str(python_exe), "-m", "pip", "install", f"{wheels[0]}[all]", "--no-warn-script-location"],
        check=True,
    )
    print("  [OK] cognithor[all] installed")

    return python_dir


def step_ollama() -> Path:
    """Step 2: Download Ollama binary."""
    print("\n=== Step 2: Ollama ===")

    ollama_dir = BUILD_DIR / "ollama"
    if ollama_dir.exists():
        print("  [SKIP] ollama/ already exists")
        return ollama_dir

    zip_path = BUILD_DIR / "downloads" / "ollama-windows.zip"
    download(OLLAMA_URL, zip_path, "Ollama for Windows")

    ollama_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(ollama_dir)
    print("  [OK] Ollama extracted")

    return ollama_dir


def step_flutter_ui() -> Path | None:
    """Step 3: Copy Flutter web UI into build dir."""
    print("\n=== Step 3: Flutter UI ===")

    # Target in build dir
    flutter_build_dest = BUILD_DIR / "flutter_web"
    if flutter_build_dest.exists():
        print("  [SKIP] flutter_web/ already in build dir")
        return flutter_build_dest

    # Source: pre-built Flutter web
    flutter_app = PROJECT_ROOT / "flutter_app"
    web_build = flutter_app / "build" / "web"

    if web_build.exists() and (web_build / "index.html").exists():
        print("  Copying pre-built Flutter web to build dir...")
        shutil.copytree(web_build, flutter_build_dest)
        print(f"  [OK] Flutter web copied ({sum(1 for _ in flutter_build_dest.rglob('*'))} files)")
        return flutter_build_dest

    # Try building if flutter available
    if not flutter_app.exists():
        print("  [SKIP] No flutter_app/ directory")
        return None

    if shutil.which("flutter") is None:
        print("  [WARN] flutter not in PATH, skipping UI build")
        return None

    print("  Building Flutter web...")
    subprocess.run(
        ["flutter", "build", "web", "--release"],
        check=True,
        cwd=str(flutter_app),
    )
    print("  [OK] Flutter web build complete")
    return web_build


def step_launcher() -> Path:
    """Step 4: Create launcher batch script."""
    print("\n=== Step 4: Launcher ===")

    launcher = BUILD_DIR / "cognithor.bat"
    launcher.write_text(
        "@echo off\r\n"
        "setlocal enabledelayedexpansion\r\n"
        "title Cognithor\r\n"
        "\r\n"
        'set "COGNITHOR_HOME=%~dp0"\r\n'
        'set "PYTHON=%COGNITHOR_HOME%python\\python.exe"\r\n'
        'set "OLLAMA=%COGNITHOR_HOME%ollama\\ollama.exe"\r\n'
        "\r\n"
        "REM Check if already running (prevent duplicate instances)\r\n"
        'netstat -ano 2>NUL | find ":8741 " | find "LISTENING" >NUL 2>NUL\r\n'
        "if not errorlevel 1 (\r\n"
        "    echo Cognithor is already running on port 8741.\r\n"
        '    start "" http://localhost:8741\r\n'
        "    timeout /t 3 /nobreak >NUL\r\n"
        "    exit /b 0\r\n"
        ")\r\n"
        "\r\n"
        "REM Verify Python exists\r\n"
        'if not exist "%PYTHON%" (\r\n'
        "    echo [ERROR] Python not found: %PYTHON%\r\n"
        "    echo Please reinstall Cognithor.\r\n"
        "    pause\r\n"
        "    exit /b 1\r\n"
        ")\r\n"
        "\r\n"
        "REM Auto-upgrade: detect source tree with newer version\r\n"
        'if exist "%COGNITHOR_HOME%auto_upgrade.py" (\r\n'
        '    "%PYTHON%" "%COGNITHOR_HOME%auto_upgrade.py"\r\n'
        ")\r\n"
        "\r\n"
        "REM First-run setup (downloads skills, installs default agents)\r\n"
        'if not exist "%USERPROFILE%\\.cognithor\\.cognithor_initialized" (\r\n'
        '    if exist "%COGNITHOR_HOME%first_run.py" (\r\n'
        "        echo Running first-time setup...\r\n"
        '        "%PYTHON%" "%COGNITHOR_HOME%first_run.py"\r\n'
        "    )\r\n"
        ")\r\n"
        "\r\n"
        "REM Start Ollama if not running\r\n"
        'if exist "%OLLAMA%" (\r\n'
        '    tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL\r\n'
        "    if errorlevel 1 (\r\n"
        "        echo Starting Ollama...\r\n"
        '        start "" "%OLLAMA%" serve\r\n'
        "        timeout /t 3 /nobreak >NUL\r\n"
        "    )\r\n"
        ")\r\n"
        "\r\n"
        "REM Start Cognithor\r\n"
        'if "%1"=="--ui" (\r\n'
        '    set "PYTHONW=%COGNITHOR_HOME%python\\pythonw.exe"\r\n'
        '    if exist "%PYTHONW%" (\r\n'
        '        start "" "%PYTHONW%" -m cognithor --no-cli --api-port 8741\r\n'
        "    ) else (\r\n"
        '        start "Cognithor Server" cmd /k ""%PYTHON%" -m cognithor --no-cli --api-port 8741"\r\n'
        "    )\r\n"
        "    echo Waiting for Cognithor to start...\r\n"
        "    set RETRIES=0\r\n"
        "    :wait_loop\r\n"
        "    timeout /t 2 /nobreak >NUL\r\n"
        '    curl -s -o NUL -w "%%{http_code}"'
        ' http://localhost:8741/api/v1/health 2>NUL | find "200" >NUL 2>NUL\r\n'
        "    if not errorlevel 1 (\r\n"
        "        echo Cognithor is ready.\r\n"
        '        start "" http://localhost:8741\r\n'
        "        exit /b 0\r\n"
        "    )\r\n"
        "    set /a RETRIES+=1\r\n"
        "    if !RETRIES! LSS 30 goto wait_loop\r\n"
        "    echo [WARN] Cognithor did not respond within 60 seconds.\r\n"
        "    echo Opening browser anyway...\r\n"
        '    start "" http://localhost:8741\r\n'
        "    exit /b 0\r\n"
        ") else (\r\n"
        '    "%PYTHON%" -m cognithor %*\r\n'
        "    if errorlevel 1 (\r\n"
        "        echo.\r\n"
        "        echo [ERROR] Cognithor exited with an error.\r\n"
        "        pause\r\n"
        "    )\r\n"
        ")\r\n",
        encoding="utf-8",
    )
    print(f"  [OK] Launcher: {launcher}")
    return launcher


def step_launcher_exe() -> Path:
    """Step 5: Build Cognithor.exe (C# app shell)."""
    print("\n=== Step 5: Launcher EXE ===")

    launcher_proj = PROJECT_ROOT / "launcher" / "Cognithor" / "Cognithor.csproj"
    if not launcher_proj.exists():
        print(f"  [SKIP] {launcher_proj} not found")
        return Path("")

    dotnet = shutil.which("dotnet")
    if dotnet is None:
        print("  [SKIP] dotnet SDK not found — using .bat launcher only")
        return Path("")

    publish_dir = BUILD_DIR / "launcher_publish"
    subprocess.run(
        [
            dotnet, "publish", str(launcher_proj),
            "-c", "Release",
            "-r", "win-x64",
            "--self-contained",
            "-p:PublishSingleFile=true",
            "-p:PublishTrimmed=true",
            "-p:TrimMode=partial",
            "-o", str(publish_dir),
        ],
        check=True,
    )

    exe = publish_dir / "Cognithor.exe"
    if not exe.exists():
        print("  [ERROR] Cognithor.exe not found after publish")
        return Path("")

    dest = BUILD_DIR / "Cognithor.exe"
    shutil.copy2(exe, dest)
    print(f"  [OK] {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return dest


def step_inno_setup(
    version: str, python_dir: Path, ollama_dir: Path, flutter_dir: Path | None
) -> Path:
    """Step 6: Compile Inno Setup installer."""
    print("\n=== Step 6: Inno Setup Compiler ===")

    iss_template = PROJECT_ROOT / "installer" / "cognithor.iss"
    if not iss_template.exists():
        print("  [ERROR] cognithor.iss not found — create it first")
        return Path("")

    # Find iscc.exe
    iscc = shutil.which("iscc")
    if iscc is None:
        # Check default locations
        for path in [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
        ]:
            if os.path.exists(path):
                iscc = path
                break

    if iscc is None:
        print(
            "  [ERROR] Inno Setup (iscc.exe) not found. Install from https://jrsoftware.org/isdl.php"
        )
        return Path("")

    # Compile
    output_dir = DIST_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use list form to avoid shell quoting issues with spaces in paths.
    cmd = [
        iscc,
        f"/DMyAppVersion={version}",
        f"/DPythonDir={python_dir}",
        f"/DOllamaDir={ollama_dir}",
        f"/DFlutterDir={flutter_dir or ''}",
        f"/DBuildDir={BUILD_DIR}",
        f"/DProjectRoot={PROJECT_ROOT}",
        f"/O{output_dir}",
        str(iss_template),
    ]
    subprocess.run(cmd, check=True)

    installers = list(output_dir.glob("CognithorSetup-*.exe"))
    if installers:
        print(
            f"  [OK] Installer: {installers[0]}"
            f" ({installers[0].stat().st_size / 1024 / 1024:.0f} MB)"
        )
        return installers[0]

    return Path("")


def main() -> int:
    print("=" * 60)
    print("  Cognithor Installer Builder")
    print("=" * 60)

    version = read_version()
    print(f"  Version: {version}")
    print(f"  Project: {PROJECT_ROOT}")
    print(f"  Build:   {BUILD_DIR}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    python_dir = step_python_embed()
    ollama_dir = step_ollama()
    flutter_dir = step_flutter_ui()
    step_launcher()
    step_launcher_exe()
    installer = step_inno_setup(version, python_dir, ollama_dir, flutter_dir)

    print("\n" + "=" * 60)
    if installer and installer.exists():
        print(f"  SUCCESS: {installer}")
        print(f"  Size: {installer.stat().st_size / 1024 / 1024:.0f} MB")
    else:
        print("  Installer build incomplete — check errors above")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
