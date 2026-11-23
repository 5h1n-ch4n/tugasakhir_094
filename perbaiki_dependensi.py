#!/usr/bin/env python3
"""Periksa dan perbaiki dependensi aplikasi Monitoring AWS.

Skrip ini dapat dijalankan dengan interpreter apa pun (system Python),
termasuk yang belum memiliki streamlit terpasang:

    python perbaiki_dependensi.py

Yang dilakukan:
  1. Menentukan interpreter Python yang dipakai.
  2. Menguji impor setiap paket yang dibutuhkan aplikasi.
  3. Memasang paket yang hilang ke interpreter tersebut.
  4. Mengulang pengujian sampai semua lolos, lalu menguji impor
     seluruh modul aplikasi.

Exit code 0 bila semua dependensi siap, 1 bila ada yang gagal.
"""

from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

#: Paket wajib: nama paket pip -> nama modul untuk impor.
PAKET = {
    "streamlit": "streamlit",
    "pandas": "pandas",
    "numpy": "numpy",
    "plotly": "plotly",
    "joblib": "joblib",
    "requests": "requests",
    "scikit-learn": "sklearn",
    "firebase-admin": "firebase_admin",
}

#: Paket yang boleh gagal tanpa menggagalkan aplikasi.
OPSIONAL = {"firebase-admin"}

#: Versi minimum yang direkomendasikan.
MINIMUM = {
    "streamlit": "1.32.0",
    "pandas": "2.1.0",
    "numpy": "1.26.0",
    "plotly": "5.20.0",
    "scikit-learn": "1.4.0",
    "joblib": "1.3.0",
    "requests": "2.31.0",
}

#: Modul aplikasi yang harus dapat diimpor.
MODUL_APP = [
    "app_config",
    "firebase_client",
    "auth_service",
    "data_service",
    "station_service",
    "ui_components",
    "pages_auth",
    "pages_dashboard",
    "pages_history",
    "pages_prediction",
    "pages_profile",
    "pages_stations",
]


def garis(teks: str = "") -> None:
    print(teks)
    print("-" * max(len(teks), 60))


def interpreter_info() -> str:
    return f"{sys.executable} (Python {sys.version.split()[0]})"


def terpasang(nama_paket: str) -> bool:
    """True bila modul paket sudah tersedia pada interpreter berjalan."""
    try:
        spec = importlib.util.find_spec(PAKET[nama_paket])
    except (ImportError, ValueError):
        return False
    return spec is not None


def versi_paket(nama_paket: str) -> str:
    try:
        mod = importlib.import_module(PAKET[nama_paket])
        return str(getattr(mod, "__version__", "tidak diketahui"))
    except Exception:
        return "tidak diketahui"


def pasang(nama_paket: str) -> bool:
    """Pasang satu paket pada interpreter berjalan.

    Sebagian distro Linux (Debian/Ubuntu recent) menandai interpreter sistem
    sebagai "externally managed" sehingga pip menolak instalasi tanpa flag
    --break-system-packages. Bila percobaan pertama ditolak dengan pesan
    tersebut, instalasi diulang memakai flag itu.
    """
    print(f"    memasang {nama_paket} ...")
    dasar = [
        sys.executable,
        "-m",
        "pip",
        "install",
        nama_paket,
        "--disable-pip-version-check",
        "--quiet",
    ]
    percobaan = [dasar, dasar + ["--break-system-packages"]]

    for perintah in percobaan:
        try:
            hasil = subprocess.run(perintah, capture_output=True, text=True, timeout=1200)
        except subprocess.TimeoutExpired:
            print("    [X] waktu instalasi habis")
            return False
        if hasil.returncode == 0:
            return True
        keluaran = (hasil.stderr or hasil.stdout or "")
        if "externally managed" in keluaran.lower() and "--break-system-packages" not in perintah:
            continue
        print("    [X] gagal:")
        for baris in keluaran.strip().splitlines()[-8:]:
            print(f"       {baris}")
        return False

    print("    [X] gagal meski sudah dicoba ulang")
    return False


def cek_versi(paket: str) -> str:
    """Beri peringatan bila versi terpasang di bawah minimum."""
    try:
        from packaging.version import Version

        terpasang_ver = Version(versi_paket(paket))
        batas = Version(MINIMUM[paket])
        if terpasang_ver < batas:
            return f"PERINGATAN: {terpasang_ver} < minimum {batas}"
    except Exception:
        pass
    return "OK"


def pasang_yang_hilang() -> list[str]:
    """Pasang seluruh paket wajib yang belum tersedia."""
    hilang = [p for p in PAKET if p not in OPSIONAL and not terpasang(p)]
    if not hilang:
        return []
    garis(f"MEMASANG {len(hilang)} PAKET: {', '.join(hilang)}")
    for paket in hilang:
        pasang(paket)
    return hilang


def pasang_opsional() -> None:
    """Pasang paket opsional bila belum ada, tanpa menggagalkan alur."""
    for paket in PAKET:
        if paket in OPSIONAL and not terpasang(paket):
            print(f"    (opsional) memasang {paket} ...")
            pasang(paket)


def verifikasi_paket() -> list[str]:
    """Cek seluruh paket, kembalikan daftar yang gagal."""
    garis("VERIFIKASI PAKET")
    gagal = []
    for paket in PAKET:
        if terpasang(paket):
            catatan = cek_versi(paket)
            tanda = "[OK]  " if catatan == "OK" else "[!]  "
            print(f"  {tanda} {paket:16s} {versi_paket(paket):16s} {catatan}")
        elif paket in OPSIONAL:
            print(f"  [!]  {paket:16s} tidak terpasang (opsional, aplikasi tetap jalan)")
        else:
            print(f"  [X]  {paket:16s} GAGAL DIPASANG")
            gagal.append(paket)
    return gagal


def verifikasi_modul() -> list[str]:
    """Uji impor seluruh modul aplikasi."""
    garis("VERIFIKASI MODUL APLIKASI")
    gagal = []
    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    for nama in MODUL_APP:
        try:
            importlib.import_module(nama)
            print(f"  [OK]  {nama}")
        except Exception as exc:
            print(f"  [X]  {nama}: {exc}")
            gagal.append(nama)
    return gagal


def main() -> int:
    garis("PERBAIKI DEPENDENSI APLIKASI MONITORING AWS")
    garis()
    print(f"  Interpreter : {interpreter_info()}")
    print(f"  Folder      : {APP_DIR}")
    print()

    garis("PEMERIKSAAN AWAL")
    for paket in PAKET:
        ada = terpasang(paket)
        tanda = "[OK]  " if ada else "[X]  "
        versi = versi_paket(paket) if ada else "BELUM TERPASANG"
        print(f"  {tanda} {paket:16s} {versi}")

    pasang_yang_hilang()
    pasang_opsional()

    gagal = verifikasi_paket()
    gagal += verifikasi_modul()

    garis()
    if gagal:
        print(f"MASIH ADA MASALAH: {', '.join(gagal)}")
        garis()
        print()
        print("Jalankan perintah ini secara manual:")
        print(f'    "{sys.executable}" -m pip install -r "{APP_DIR / "requirements.txt"}"')
        print()
        return 1

    print("SEMUA DEPENDENSI SIAP.")
    garis()
    print()
    print("Jalankan aplikasi:")
    print(f'    "{sys.executable}" -m streamlit run app.py')
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
