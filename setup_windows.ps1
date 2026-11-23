# ============================================================
#  Setup Windows untuk aplikasi Streamlit Monitoring AWS
#  Jalankan di PowerShell dari folder streamlit_app:
#      powershell -ExecutionPolicy Bypass -File setup_windows.ps1
# ============================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Setup Aplikasi Streamlit Monitoring AWS" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# ------------------------------------------------------------
# 1. Pastikan Python 3.11+ tersedia
# ------------------------------------------------------------
$pythonCmd = $null
foreach ($cmd in @("python", "py", "python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $ver -match "(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                $pythonCmd = $cmd
                Write-Host "[OK] Python $ver dipakai via '$cmd'" -ForegroundColor Green
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host "[X] Python 3.10+ tidak ditemukan." -ForegroundColor Red
    Write-Host "    Unduh dari https://www.python.org/downloads/ lalu ulangi." -ForegroundColor Yellow
    exit 1
}

# ------------------------------------------------------------
# 2. Virtual environment
#    Prioritaskan venv yang sudah ada agar dependensi yang sudah
#    terpasang tidak terbuang. Venv dapat bernama ".venv" atau "venv".
# ------------------------------------------------------------
$venvPath = $null
$venvPython = $null

foreach ($candidate in @(".venv", "venv")) {
    $path = Join-Path $PSScriptRoot $candidate
    $exe = Join-Path $path "Scripts\python.exe"
    if (Test-Path $exe) {
        $venvPath = $path
        $venvPython = $exe
        Write-Host "[OK] Virtual environment ditemukan: $candidate" -ForegroundColor Green
        break
    }
}

if (-not $venvPython) {
    $venvPath = Join-Path $PSScriptRoot ".venv"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    Write-Host ""
    Write-Host "[..] Membuat virtual environment di .venv" -ForegroundColor Cyan
    & $pythonCmd -m venv $venvPath
    if (-not (Test-Path $venvPython)) {
        Write-Host "[X] Gagal membuat virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "[OK] Virtual environment dibuat" -ForegroundColor Green
}

# Selalu pakai interpreter dari venv mulai titik ini.
$pythonCmd = $venvPython
$pipCmd = Join-Path $venvPath "Scripts\pip.exe"

# ------------------------------------------------------------
# 3. Upgrade pip
# ------------------------------------------------------------
Write-Host ""
Write-Host "[..] Memperbarui pip" -ForegroundColor Cyan
& $pipCmd install --upgrade pip --quiet --disable-pip-version-check
Write-Host "[OK] pip diperbarui" -ForegroundColor Green

# ------------------------------------------------------------
# 4. Pasang dependensi
# ------------------------------------------------------------
Write-Host ""
Write-Host "[..] Memasang dependensi dari requirements.txt (mungkin 1-3 menit)" -ForegroundColor Cyan
& $pipCmd install -r requirements.txt --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Instalasi dependensi gagal." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Dependensi terpasang" -ForegroundColor Green

# firebase_admin bersifat opsional (ada fallback REST). Pasang terpisah
# bila Anda ingin memakai Firebase Admin SDK.
Write-Host ""
Write-Host "[..] Memasang firebase-admin (opsional, untuk Firebase Admin SDK)" -ForegroundColor Cyan
& $pipCmd install firebase-admin --quiet --disable-pip-version-check
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] firebase-admin terpasang" -ForegroundColor Green
} else {
    Write-Host "[!] firebase-admin gagal dipasang. Aplikasi tetap jalan via REST API." -ForegroundColor Yellow
}

# ------------------------------------------------------------
# 5. Verifikasi menyeluruh (memakai skrip perbaikan dependensi)
# ------------------------------------------------------------
Write-Host ""
Write-Host "[..] Memverifikasi instalasi dan seluruh modul aplikasi" -ForegroundColor Cyan
& $pythonCmd -u (Join-Path $PSScriptRoot "perbaiki_dependensi.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Verifikasi gagal." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------
# 6. Periksa secrets.toml
# ------------------------------------------------------------
Write-Host ""
$secretsPath = Join-Path $PSScriptRoot ".streamlit\secrets.toml"
if (Test-Path $secretsPath) {
    Write-Host "[OK] .streamlit\secrets.toml ditemukan" -ForegroundColor Green
} else {
    Write-Host "[!] .streamlit\secrets.toml belum ada." -ForegroundColor Yellow
    Write-Host "    Aplikasi tetap berjalan pada mode lokal (data contoh)." -ForegroundColor Yellow
    Write-Host "    Untuk memakai Firebase, buat file tersebut dengan isi:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host '    [firebase]' -ForegroundColor DarkGray
    Write-Host '    database_url = "https://<PROJECT_ID>.firebaseio.com"' -ForegroundColor DarkGray
    Write-Host '    api_key = "<WEB_API_KEY>"' -ForegroundColor DarkGray
    Write-Host ""
}

# ------------------------------------------------------------
# 7. Selesai
# ------------------------------------------------------------
Write-Host ""
Write-Host "==================================================" -ForegroundColor Green
Write-Host " Instalasi selesai." -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Jalankan aplikasi:" -ForegroundColor Cyan
Write-Host "    cd `"$PSScriptRoot`"" -ForegroundColor White
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "    streamlit run app.py" -ForegroundColor White
Write-Host ""
Write-Host "Tanpa aktivasi venv, jalankan langsung:" -ForegroundColor Cyan
Write-Host "    .\.venv\Scripts\streamlit.exe run app.py" -ForegroundColor White
Write-Host ""
