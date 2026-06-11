@echo off
setlocal

echo ============================================================
echo  KindleFeeder Installer
echo ============================================================
echo.

set INSTALL_DIR=C:\KindleFeeder

REM ── 1. Copy files ─────────────────────────────────────────────────────────────
echo Installing files to %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%\host" mkdir "%INSTALL_DIR%\host"
if not exist "%INSTALL_DIR%\tray" mkdir "%INSTALL_DIR%\tray"
xcopy /E /I /Y "%~dp0host\*"      "%INSTALL_DIR%\host\"      >nul
xcopy /E /I /Y "%~dp0tray\*"      "%INSTALL_DIR%\tray\"      >nul
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
