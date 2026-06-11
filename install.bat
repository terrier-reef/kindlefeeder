@echo off
setlocal

echo ============================================================
echo  KindleFeeder Installer
echo ============================================================
echo.

REM ── 1. Copy files to a stable location ───────────────────────────────────────
set INSTALL_DIR=C:\KindleFeeder
echo Installing files to %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%\host" mkdir "%INSTALL_DIR%\host"
xcopy /E /I /Y "%~dp0host\*" "%INSTALL_DIR%\host\" >nul
xcopy /E /I /Y "%~dp0extension\*" "%INSTALL_DIR%\extension\" >nul 2>&1

REM ── 2. Update the manifest path (it already points to C:\KindleFeeder\host) ──

REM ── 3. Register native messaging host in HKCU (no admin needed) ──────────────
echo Registering native messaging host...
reg add "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.kindlefeeder.host" ^
    /ve /t REG_SZ /d "%INSTALL_DIR%\host\com.kindlefeeder.host.json" /f >nul

if %errorlevel% neq 0 (
    echo ERROR: Failed to write registry key.
    pause
    exit /b 1
)

REM ── 4. Create queue folder ────────────────────────────────────────────────────
if not exist "%APPDATA%\KindleFeeder\queue" mkdir "%APPDATA%\KindleFeeder\queue"

REM ── 5. Check Python ───────────────────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Python not found in PATH.
    echo Download Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
)

REM ── 6. Check Calibre ─────────────────────────────────────────────────────────
if exist "C:\Program Files\Calibre2\ebook-convert.exe" (
    echo Calibre found at C:\Program Files\Calibre2\
) else if exist "C:\Program Files (x86)\Calibre2\ebook-convert.exe" (
    echo Calibre found at C:\Program Files (x86)\Calibre2\
) else (
    echo.
    echo WARNING: Calibre not found.
    echo Download Calibre from: https://calibre-ebook.com/download_windows
    echo.
)

echo.
echo ============================================================
echo  Installation complete!
echo.
echo  Next step: Load the Chrome extension
echo    1. Open Chrome and go to: chrome://extensions
echo    2. Enable "Developer mode" (top right toggle)
echo    3. Click "Load unpacked"
echo    4. Select: %INSTALL_DIR%\extension
echo    5. Copy the Extension ID shown and paste it into:
echo       %INSTALL_DIR%\host\com.kindlefeeder.host.json
echo       (replace REPLACE_WITH_YOUR_EXTENSION_ID)
echo    6. Re-run this installer OR manually re-run step 3 above
echo       to re-register the manifest after updating the ID.
echo ============================================================
echo.
pause
