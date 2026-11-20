@echo off
setlocal
cd /d "%~dp0"
set "VERSION=1.1"
echo ==============================================
echo Building Desktop GIF Sticker v%VERSION% - exe + installer
echo ==============================================
echo.
py -c "import PyInstaller, PyQt6, PIL" >nul 2>nul
if errorlevel 1 (
    echo Library build belum lengkap. Jalankan dulu:
    echo     py -m pip install -r requirements.txt pyinstaller
    pause
    exit /b 1
)

echo [1/3] Running PyInstaller...
py -m PyInstaller DesktopSticker.spec --noconfirm
if errorlevel 1 (
    echo PyInstaller build failed!
    pause
    exit /b 1
)
echo.
echo [2/3] Compiling Inno Setup Installer...
set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    echo ERROR: ISCC.exe tidak ditemukan. Install Inno Setup 6 dari https://jrsoftware.org/isdl.php
    echo dist\DesktopSticker_Portable.exe sudah jadi, tapi installer belum dibuat.
    pause
    exit /b 1
)
"%ISCC_PATH%" /DMyAppVersion=%VERSION% installer.iss
if errorlevel 1 (
    echo Inno Setup build failed!
    pause
    exit /b 1
)
echo.
echo [3/3] Updating ZIP distribution...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\DesktopSticker_Setup_v%VERSION%.exe' -DestinationPath 'dist\DesktopSticker_Setup_v%VERSION%.zip' -Force"
echo.
echo Build completed successfully! Output in dist\
echo   - dist\DesktopSticker_Portable.exe         (portable, 1 file)
echo   - dist\DesktopSticker_Setup_v%VERSION%.exe (installer)
echo   - dist\DesktopSticker\                     (isi aplikasi untuk installer)
pause
