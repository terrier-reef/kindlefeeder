@echo off
setlocal

echo ============================================================
echo  KindleFeeder Installer
echo ============================================================
echo.

set INSTALL_DIR=C:\KindleFeeder

REM ── 1. Copy files ─────────────────────────────────────────────────────────────
echo Installing files to %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%\host"   mkdir "%INSTALL_DIR%\host"
if not exist "%INSTALL_DIR%\tray"   mkdir "%INSTALL_DIR%\tray"
if not exist "%INSTALL_DIR%\digest" mkdir "%INSTALL_DIR%\digest"
xcopy /E /I /Y "%~dp0host\*"      "%INSTALL_DIR%\host\"      >nul
xcopy /E /I /Y "%~dp0tray\*"      "%INSTALL_DIR%\tray\"      >nul
xcopy /E /I /Y "%~dp0digest\*"    "%INSTALL_DIR%\digest\"    >nul
xcopy /E /I /Y "%~dp0extension\*" "%INSTALL_DIR%\extension\" >nul 2>&1

REM ── 2. Register native messaging host in HKCU (no admin needed) ──────────────
echo Registering native messaging host...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.kindlefeeder.host" ^
    /ve /t REG_SZ /d "%INSTALL_DIR%\host\com.kindlefeeder.host.json" /f >nul
if %errorlevel% neq 0 (
    echo ERROR: Failed to write registry key.
    pause
    exit /b 1
)

REM ── 3. Create folders ─────────────────────────────────────────────────────────
if not exist "%APPDATA%\KindleFeeder\queue" mkdir "%APPDATA%\KindleFeeder\queue"

REM ── 4. Check Python ───────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Python not found in PATH.
    echo Download Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM ── 5. Install all Python dependencies ───────────────────────────────────────
echo Installing Python dependencies...
python -m pip install --quiet ^
    pystray Pillow ^
    feedparser requests readability-lxml lxml beautifulsoup4 ^
    browser-cookie3 anthropic
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your Python installation.
    pause
    exit /b 1
)

REM ── 6. Find pythonw.exe ───────────────────────────────────────────────────────
for /f "delims=" %%i in ('where python') do (
    set PYTHON_PATH=%%i
    goto :found_python
)
:found_python
set PYTHONW_PATH=%PYTHON_PATH:python.exe=pythonw.exe%

REM ── 7. Register both tray apps to run at Windows startup ─────────────────────
echo Registering tray apps to run at startup...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "KindleFeeder" ^
    /t REG_SZ ^
    /d "\"%PYTHONW_PATH%\" \"%INSTALL_DIR%\tray\kindlefeeder_tray.py\"" ^
    /f >nul

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "KindleFeederDigest" ^
    /t REG_SZ ^
    /d "\"%PYTHONW_PATH%\" \"%INSTALL_DIR%\digest\kindlefeeder_digest_tray.py\"" ^
    /f >nul

REM ── 8. Check Calibre ─────────────────────────────────────────────────────────
if exist "C:\Program Files\Calibre2\ebook-convert.exe" (
    echo Calibre found.
) else if exist "C:\Program Files (x86)\Calibre2\ebook-convert.exe" (
    echo Calibre found.
) else (
    echo.
    echo WARNING: Calibre not found.
    echo Download Calibre from: https://calibre-ebook.com/download_windows
    echo.
)

REM ── 9. Check Anthropic API key ────────────────────────────────────────────────
if "%ANTHROPIC_API_KEY%"=="" (
    echo.
    echo NOTE: ANTHROPIC_API_KEY is not set as a system environment variable.
    echo The digest will not run until you add your API key in the
    echo "Digest Settings" window (right-click the blue tray icon).
    echo Get a key at: https://console.anthropic.com/
    echo.
)

REM ── 10. Start both trays now ──────────────────────────────────────────────────
echo Starting tray apps...
start "" "%PYTHONW_PATH%" "%INSTALL_DIR%\tray\kindlefeeder_tray.py"
start "" "%PYTHONW_PATH%" "%INSTALL_DIR%\digest\kindlefeeder_digest_tray.py"

echo.
echo ============================================================
echo  Installation complete!
echo.
echo  Green icon  = Kindle sync (sends articles from Chrome extension)
echo  Blue icon   = Daily Digest (fetches opinion pages each morning)
echo.
echo  First time setup for the digest:
echo    Right-click the BLUE tray icon ^> "Digest Settings"
echo    Paste your Anthropic API key and click Save ^& Close.
echo.
echo  Chrome extension setup:
echo    1. Open Chrome ^> chrome://extensions
echo    2. Enable "Developer mode"
echo    3. Click "Load unpacked" ^> select: %INSTALL_DIR%\extension
echo    4. Copy the Extension ID into:
echo       %INSTALL_DIR%\host\com.kindlefeeder.host.json
echo    5. Re-run this installer to re-register.
echo ============================================================
echo.
pause


REM ── 2. Register native messaging host in HKCU (no admin needed) ──────────────
echo Registering native messaging host...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.kindlefeeder.host" ^
    /ve /t REG_SZ /d "%INSTALL_DIR%\host\com.kindlefeeder.host.json" /f >nul
if %errorlevel% neq 0 (
    echo ERROR: Failed to write registry key.
    pause
    exit /b 1
)

REM ── 3. Create queue folder ────────────────────────────────────────────────────
if not exist "%APPDATA%\KindleFeeder\queue" mkdir "%APPDATA%\KindleFeeder\queue"

REM ── 4. Check Python ───────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Python not found in PATH.
    echo Download Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

REM ── 5. Install Python dependencies ───────────────────────────────────────────
echo Installing Python dependencies (pystray, Pillow)...
python -m pip install --quiet pystray Pillow
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Check your Python installation.
    pause
    exit /b 1
)

REM ── 6. Register tray app to run at Windows startup (no console window) ────────
echo Registering tray app to run at startup...

REM Find pythonw.exe (same directory as python.exe)
for /f "delims=" %%i in ('where python') do (
    set PYTHON_PATH=%%i
    goto :found_python
)
:found_python
set PYTHONW_PATH=%PYTHON_PATH:python.exe=pythonw.exe%

reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" ^
    /v "KindleFeeder" ^
    /t REG_SZ ^
    /d "\"%PYTHONW_PATH%\" \"%INSTALL_DIR%\tray\kindlefeeder_tray.py\"" ^
    /f >nul

REM ── 7. Check Calibre ─────────────────────────────────────────────────────────
if exist "C:\Program Files\Calibre2\ebook-convert.exe" (
    echo Calibre found.
) else if exist "C:\Program Files (x86)\Calibre2\ebook-convert.exe" (
    echo Calibre found.
) else (
    echo.
    echo WARNING: Calibre not found.
    echo Download Calibre from: https://calibre-ebook.com/download_windows
    echo.
)

REM ── 8. Start tray now (without waiting for a reboot) ─────────────────────────
echo Starting tray app...
start "" "%PYTHONW_PATH%" "%INSTALL_DIR%\tray\kindlefeeder_tray.py"

echo.
echo ============================================================
echo  Installation complete!
echo  A green KindleFeeder icon should appear in your system tray.
echo.
echo  Next step: Load the Chrome extension
echo    1. Open Chrome and go to: chrome://extensions
echo    2. Enable "Developer mode" (top right toggle)
echo    3. Click "Load unpacked"
echo    4. Select: %INSTALL_DIR%\extension
echo    5. Copy the Extension ID shown and paste it into:
echo       %INSTALL_DIR%\host\com.kindlefeeder.host.json
echo    6. Re-run this installer to re-register after updating the ID.
echo ============================================================
echo.
pause
