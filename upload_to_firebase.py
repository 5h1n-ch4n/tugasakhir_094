import os
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db

# Konfigurasi
CRED_FILE = "serviceAccountKey.json"
CSV_FILE = "data/raw_history.csv"
FIREBASE_HISTORY_PATH = "aws_data/AWS_TPST_01/history"

# Jumlah baris terakhir yang diunggah (5000 baris = ~3,5 hari data per menit, sesuai batas pembacaan)
JUMLAH_BARIS = 5000


def main():
    db_url = os.environ.get("FIREBASE_DB_URL")
    if not db_url:
        db_url = input("Masukkan FIREBASE_DB_URL Anda: ").strip()

    if not os.path.exists(CRED_FILE):
        print(f"[ERROR] File '{CRED_FILE}' tidak ditemukan di folder proyek.")
        return

    if not os.path.exists(CSV_FILE):
        print(f"[ERROR] File '{CSV_FILE}' belum ada. Jalankan 'python generate_data.py' dulu.")
        return

    # Inisialisasi Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate(CRED_FILE)
        firebase_admin.initialize_app(cred, {"databaseURL": db_url})

    # Ambil N baris terakhir agar proses upload cepat (1-2 detik)
    df = pd.read_csv(CSV_FILE).tail(JUMLAH_BARIS)

    # Susun format JSON sesuai skema ESP32 & preprocess.py
    batch_payload = {}
    for _, row in df.iterrows():
        ts = int(row["timestamp"])
        key = f"sim_{ts}"
        record = {
            "timestamp": ts,
            "cuaca": {
                "suhu_c": round(float(row["suhu"]), 2),
                "kelembapan_persen": round(float(row["kelembapan"]), 2),
                "tekanan_hpa": round(float(row["tekanan"]), 2),
                "cahaya_lux": round(float(row["cahaya"]), 2),
                "hujan_interval_mm": round(float(row["hujan"]), 4),
                "angin_kmh": round(float(row["kecepatan_angin"]), 2),
            },
        }
        if "tegangan_v" in row and "arus_ma" in row and "daya_mw" in row:
            record["daya_ina226"] = {
                "tegangan_v": round(float(row["tegangan_v"]), 3),
                "arus_ma": round(float(row["arus_ma"]), 2),
                "daya_mw": round(float(row["daya_mw"]), 1),
            }
        batch_payload[key] = record

    print(f"Mengunggah {len(batch_payload)} rekaman ke '{FIREBASE_HISTORY_PATH}'...")
    ref = db.reference(FIREBASE_HISTORY_PATH)
    ref.update(batch_payload)
    print("[OK] Dataset simulasi berhasil masuk ke Firebase Realtime Database!")


if __name__ == "__main__":
    main()