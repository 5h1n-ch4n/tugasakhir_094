#!/usr/bin/env bash
# ============================================================
#  Setup Linux/macOS untuk aplikasi Streamlit Monitoring AWS
#  Jalankan:  bash setup.sh
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

echo ""
echo "=================================================="
echo " Setup Aplikasi Streamlit Monitoring AWS"
echo "=================================================="
echo ""

# --- 1. Pastikan Python 3.10+ tersedia ---
PY=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        ver="$("$cmd" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
        major="${ver%%.*}"
        minor="${ver##*.}"
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
            PY="$cmd"
            echo "[OK] Python $ver dipakai via '$cmd'"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "[X] Python 3.10+ tidak ditemukan."
    echo "    Instalasi:  sudo apt install python3 python3-venv   (Debian/Ubuntu)"
    echo "             atau  brew install python@3.11               (macOS)"
    exit 1
fi

# --- 2. Virtual environment ---
if [ ! -x ".venv/bin/python" ]; then
    echo ""
    echo "[..] Membuat virtual environment di .venv"
    "$PY" -m venv .venv
    echo "[OK] Virtual environment dibuat"
else
    echo "[OK] Virtual environment sudah ada"
fi

VPY=".venv/bin/python"
VPIP=".venv/bin/pip"

# --- 3. Upgrade pip ---
echo ""
echo "[..] Memperbarui pip"
"$VPIP" install --upgrade pip --quiet

# --- 4. Dependensi ---
echo ""
echo "[..] Memasang dependensi dari requirements.txt (mungkin 1-3 menit)"
"$VPIP" install -r requirements.txt --quiet

echo "[..] Memasang firebase-admin (opsional, untuk Firebase Admin SDK)"
"$VPIP" install firebase-admin --quiet || \
    echo "[!] firebase-admin gagal dipasang. Aplikasi tetap jalan via REST API."

# --- 5. Verifikasi menyeluruh (termasuk impor seluruh modul aplikasi) ---
echo ""
echo "[..] Memverifikasi instalasi"
"$VPY" perbaiki_dependensi.py
if [ $? -ne 0 ]; then
    echo "[X] Verifikasi gagal."
    exit 1
fi

# --- 6. Periksa secrets.toml ---
echo ""
if [ -f ".streamlit/secrets.toml" ]; then
    echo "[OK] .streamlit/secrets.toml ditemukan"
else
    echo "[!] .streamlit/secrets.toml belum ada."
    echo "    Aplikasi berjalan pada mode lokal (data contoh)."
    echo "    Untuk memakai Firebase, buat file tersebut:"
    echo ""
    echo "        [firebase]"
    echo "        database_url = \"https://<PROJECT_ID>.firebaseio.com\""
    echo "        api_key = \"<WEB_API_KEY>\""
    echo ""
fi

echo ""
echo "=================================================="
echo " Instalasi selesai."
echo "=================================================="
echo ""
echo "Jalankan aplikasi:"
echo "    source .venv/bin/activate"
echo "    streamlit run app.py"
echo ""
echo "Atau tanpa aktivasi:"
echo "    .venv/bin/streamlit run app.py"
echo ""
