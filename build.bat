@echo off
echo ==============================================
echo Building Desktop GIF Sticker Binary & Installer
echo ==============================================
echo.
echo [1/3] Running PyInstaller...
py -m PyInstaller DesktopSticker.spec --noconfirm
if %errorlevel% neq 0 (
    echo PyInstaller build failed!
    pause
    exit /b %errorlevel%
)
echo.
echo [2/3] Compiling Inno Setup Installer...
set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"

if exist "%ISCC_PATH%" (
    "%ISCC_PATH%" installer.iss
) else (
    echo WARNING: ISCC.exe not found.
)
echo.
echo [3/3] Updating ZIP distribution...
powershell -NoProfile -Command "if (Test-Path 'dist\DesktopSticker_Setup_v1.0.exe') { Compress-Archive -Path 'dist\DesktopSticker_Setup_v1.0.exe' -DestinationPath 'dist\DesktopSticker_Setup_v1.0.zip' -Force }"
echo.
echo Build completed successfully! Output in dist/
