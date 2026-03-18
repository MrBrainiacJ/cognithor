@echo off
setlocal enabledelayedexpansion
title Cognithor Control Center
color 0F

:: ============================================================
::  COGNITHOR ONE-CLICK LAUNCHER
::  Prueft Abhaengigkeiten, bootstrappt beim ersten Start,
::  startet dann die Web-UI.
::
::  Alle Logik in :main, damit das pause am Ende IMMER greift.
:: ============================================================

call :main
echo.
echo   ============================================================
echo   Press any key to close this window...
echo   ============================================================
pause >nul
exit /b 0

:: ============================================================
:main
:: ============================================================

:: UTF-8 fuer Python-Output aktivieren
chcp 65001 >nul 2>&1

echo.
echo    ____  ___   ____ _   _ ___ _____ _   _  ___  ____
echo   / ___^|/ _ \ / ___^| \ ^| ^|_ _^|_   _^| ^| ^| ^|/ _ \^|  _ \
echo  ^| ^|   ^| ^| ^| ^| ^|  _^|  \^| ^|^| ^|  ^| ^| ^| ^|_^| ^| ^| ^| ^| ^|_^) ^|
echo  ^| ^|___^| ^|_^| ^| ^|_^| ^| ^|\  ^|^| ^|  ^| ^| ^|  _  ^| ^|_^| ^|  _ ^<
echo   \____^|\___/ \____^|_^| \_^|___^| ^|_^| ^|_^| ^|_^|\___/^|_^| \_\
echo.

set "REPO_ROOT=%~dp0"
:: Trailing backslash entfernen
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

:: ============================================================
::  1. Python im PATH?
:: ============================================================
call :find_python
if "!PYTHON_CMD!"=="" (
    echo   [ERROR] Python not found!
    echo.
    echo   Please install Python 3.12+:
    echo   https://www.python.org/downloads/
    echo.
    echo   IMPORTANT: Check "Add Python to PATH" during installation!
    goto :eof
)

:: ============================================================
::  2. Python >= 3.12?
:: ============================================================
%PYTHON_CMD% -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)" 2>nul
if errorlevel 1 (
    echo   [ERROR] Python 3.12 or newer is required!
    echo.
    for /f "tokens=*" %%v in ('%PYTHON_CMD% --version 2^>^&1') do echo   Installed: %%v
    echo.
    echo   Please upgrade Python:
    echo   https://www.python.org/downloads/
    goto :eof
)

:: ============================================================
::  3. Flutter / Node.js erkennen
:: ============================================================
call :detect_flutter
call :detect_node

:: ============================================================
::  4. Bootstrap ausfuehren
:: ============================================================
echo   Starting bootstrap...
echo.

%PYTHON_CMD% "%REPO_ROOT%\scripts\bootstrap_windows.py" --repo-root "%REPO_ROOT%"
if errorlevel 1 (
    echo.
    echo   [ERROR] Bootstrap failed!
    echo   Please check the output above for details.
    goto :eof
)

:: ============================================================
::  5. UI-Modus waehlen
:: ============================================================

:: --- Modus A: Flutter vorhanden ---
if "!HAS_FLUTTER!"=="0" goto :check_node_ui
if not exist "%REPO_ROOT%\flutter_app\pubspec.yaml" goto :check_node_ui
echo.
echo   Flutter detected.

:: Flutter Dependencies holen (nur einmal noetig)
if not exist "%REPO_ROOT%\flutter_app\.dart_tool" (
    echo   [INFO] Fetching Flutter dependencies...
    cd /d "%REPO_ROOT%\flutter_app"
    cmd /c flutter pub get >nul 2>&1
    cd /d "%REPO_ROOT%"
)

:: Auto-build Flutter Web if SDK available but no build
if not exist "%REPO_ROOT%\flutter_app\build\web\index.html" (
    echo   [INFO] Building Flutter Web UI...
    cd /d "%REPO_ROOT%\flutter_app"
    cmd /c flutter build web --release >nul 2>&1
    cd /d "%REPO_ROOT%"
    if exist "%REPO_ROOT%\flutter_app\build\web\index.html" (
        echo   [OK] Flutter Web UI built successfully.
    ) else (
        echo   [WARNING] Flutter build failed. Falling back...
    )
)

:: Pre-built Flutter Web vorhanden? Backend serviert es direkt
if exist "%REPO_ROOT%\flutter_app\build\web\index.html" (
    echo   Starting backend with Flutter UI...
    echo   Backend + UI at http://localhost:8741
    echo.
    cd /d "%REPO_ROOT%"
    start "" http://localhost:8741
    %PYTHON_CMD% -m jarvis --no-cli
    echo.
    echo   Cognithor stopped.
    goto :eof
)

:: Flutter Dev-Modus: Backend im Hintergrund, Flutter im Vordergrund
echo   Starting backend...
cd /d "%REPO_ROOT%"
start "" /b %PYTHON_CMD% -m jarvis --no-cli

:: Warten bis Backend antwortet
call :wait_for_backend

echo   Starting Flutter Web UI (dev mode)...
echo   Open http://127.0.0.1:5173 in your browser.
echo.
cd /d "%REPO_ROOT%\flutter_app"
cmd /c flutter run -d chrome --web-port 5173
if errorlevel 1 (
    echo.
    echo   [INFO] Chrome mode failed. Trying web-server mode...
    cmd /c flutter run -d web-server --web-port 5173
)
call :stop_backend
goto :eof

:: --- Modus B: Node.js vorhanden -> Vite Dev Server (Legacy/DEPRECATED) ---
:check_node_ui
echo.
echo   [DEPRECATED] React UI is deprecated. Please install Flutter.
echo   https://docs.flutter.dev/get-started/install
echo.
:: Still fall through to pre-built check
goto :check_prebuilt

:: --- Modus C: Pre-built React UI (DEPRECATED) ---
:check_prebuilt
if not exist "%REPO_ROOT%\ui\dist\index.html" goto :check_flutter_prebuilt
echo.
echo   [DEPRECATED] React UI is deprecated. Please install Flutter.
echo   https://docs.flutter.dev/get-started/install
echo.
echo   Node.js not found -- starting pre-built UI.
echo   Backend + UI at http://localhost:8741
echo.
cd /d "%REPO_ROOT%"
start "" http://localhost:8741
%PYTHON_CMD% -m jarvis --no-cli
echo.
echo   Cognithor stopped.
goto :eof

:: --- Modus D: Flutter pre-built Web (ohne Flutter SDK) ---
:check_flutter_prebuilt
if not exist "%REPO_ROOT%\flutter_app\build\web\index.html" goto :cli_fallback
echo.
echo   Starting with pre-built Flutter UI...
echo   Backend + UI at http://localhost:8741
echo.
cd /d "%REPO_ROOT%"
start "" http://localhost:8741
%PYTHON_CMD% -m jarvis --no-cli
echo.
echo   Cognithor stopped.
goto :eof

:: --- Modus E: CLI-Fallback ---
:cli_fallback
echo.
echo   No UI toolkit found. Starting in CLI mode.
echo.
echo   For the Flutter UI (recommended):
echo     1. Install Flutter: https://docs.flutter.dev/get-started/install
echo     2. Run: flutter pub get (in flutter_app/)
echo.
echo   ============================================================
cd /d "%REPO_ROOT%"
%PYTHON_CMD% -m jarvis
echo.
echo   Cognithor stopped.
goto :eof

:: ============================================================
::  SUBROUTINEN
:: ============================================================

:find_python
set "PYTHON_CMD="
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if "!PYTHON_CMD!"=="" (
    where py >nul 2>&1
    if not errorlevel 1 (
        py -c "import sys" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=py"
    )
)
goto :eof

:detect_flutter
set "HAS_FLUTTER=0"
where flutter >nul 2>&1
if not errorlevel 1 (
    cmd /c flutter --version >nul 2>&1
    if not errorlevel 1 set "HAS_FLUTTER=1"
)
if "!HAS_FLUTTER!"=="0" (
    if exist "C:\flutter\bin\flutter.bat" (
        set "PATH=C:\flutter\bin;!PATH!"
        cmd /c C:\flutter\bin\flutter.bat --version >nul 2>&1
        if not errorlevel 1 set "HAS_FLUTTER=1"
    )
)
goto :eof

:detect_node
set "HAS_NODE=0"
where node >nul 2>&1
if not errorlevel 1 set "HAS_NODE=1"
goto :eof

:wait_for_backend
echo   Waiting for backend...
for /l %%i in (1,1,15) do (
    if "!BACKEND_READY!" neq "1" (
        curl -sf http://localhost:8741/api/v1/health >nul 2>&1
        if not errorlevel 1 (
            set "BACKEND_READY=1"
        ) else (
            timeout /t 1 /nobreak >nul
        )
    )
)
if "!BACKEND_READY!" neq "1" (
    echo   [WARNING] Backend did not respond within 15s. Continuing...
) else (
    echo   Backend ready.
)
echo.
goto :eof

:stop_backend
echo.
echo   Stopping backend...
taskkill /f /fi "WINDOWTITLE eq Cognithor*" >nul 2>&1
%PYTHON_CMD% -c "import os,signal;[os.kill(int(l.split()[1]),signal.SIGTERM) for l in __import__('subprocess').check_output('tasklist /fi \"IMAGENAME eq python.exe\" /fo list /nh',shell=True).decode().split('PID:')[1:] if 'jarvis' in l.lower()]" >nul 2>&1
echo   Cognithor stopped.
goto :eof
