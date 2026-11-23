@echo off
REM ============================================================
REM  Jalankan aplikasi Streamlit Monitoring AWS
REM  Klik ganda file ini, atau jalankan:  jalankan.bat
REM
REM  Skrip ini otomatis memasang dependensi yang kurang sebelum
REM  menjalankan aplikasi, sehingga tidak pernah gagal dengan
REM  "ModuleNotFoundError: No module named 'streamlit'" atau
REM  "No module named 'plotly'".
REM ============================================================

cd /d "%~dp0"
setlocal

echo.
echo ==================================================
echo  Coop Master - Smart Poultry ^& PLTS Monitoring
echo ==================================================
echo.

REM --- 1. Temukan virtual environment yang sudah ada ---
set "VPY="
set "VSTREAMLIT="

if exist ".venv\Scripts\python.exe" (
    set "VPY=.venv\Scripts\python.exe"
    set "VSTREAMLIT=.venv\Scripts\streamlit.exe"
    echo [OK] Virtual environment ditemukan: .venv
) else if exist "venv\Scripts\python.exe" (
    set "VPY=venv\Scripts\python.exe"
    set "VSTREAMLIT=venv\Scripts\streamlit.exe"
    echo [OK] Virtual environment ditemukan: venv
)

REM --- 2. Buat bila belum ada ---
if not defined VPY (
    echo [..] Virtual environment belum ada, membuat...
    python -m venv .venv 2>nul
    if not exist ".venv\Scripts\python.exe" (
        py -3 -m venv .venv 2>nul
    )
    if not exist ".venv\Scripts\python.exe" (
        echo.
        echo [X] Gagal membuat virtual environment.
        echo     Pastikan Python 3.10+ sudah terpasang dan ada di PATH.
        echo     Unduh dari https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    set "VPY=.venv\Scripts\python.exe"
    set "VSTREAMLIT=.venv\Scripts\streamlit.exe"
    echo [OK] Virtual environment dibuat
)

REM --- 3. Perbaiki dependensi yang kurang ---
echo.
echo [..] Memeriksa dan melengkapi dependensi...
"%VPY%" -u perbaiki_dependensi.py
if errorlevel 1 (
    echo.
    echo [X] Dependensi belum lengkap. Coba jalankan manual:
    echo     "%VPY%" -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM --- 4. Jalankan aplikasi ---
echo.
echo [..] Menjalankan Streamlit...
echo     Buka http://localhost:8501 di peramban
echo     Tekan Ctrl+C untuk menghentikan.
echo.

"%VSTREAMLIT%" run app.py

echo.
echo Aplikasi berhenti.
pause
