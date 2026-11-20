@echo off
setlocal
cd /d "%~dp0"

rem Cari Python: py launcher dulu, lalu python
set "PY="
set "PYW="
where py >nul 2>nul && (set "PY=py" & set "PYW=pyw")
if not defined PY where python >nul 2>nul && (set "PY=python" & set "PYW=pythonw")
if not defined PY (
    echo Python tidak ditemukan. Install Python dari https://www.python.org
    pause
    exit /b 1
)

rem Cek library. Tanpa ini, pyw gagal diam-diam dan stiker tidak muncul.
%PY% -c "import PyQt6, PIL" >nul 2>nul
if errorlevel 1 (
    echo Library yang dibutuhkan belum terinstall: PyQt6 / Pillow
    choice /m "Install sekarang"
    if errorlevel 2 exit /b 1
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Install gagal. Coba jalankan manual: %PY% -m pip install -r requirements.txt
        pause
        exit /b 1
    )
)

rem Jalankan tanpa jendela console
start "" %PYW% "%~dp0main.py"
