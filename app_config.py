"""
Konfigurasi aplikasi Streamlit Monitoring AWS & Prediksi Cuaca SVM.

Modul ini HANYA berisi konfigurasi read-only. Tidak mengubah atau memodifikasi
file pipeline Python yang sudah ada (aws-svm-pejantan/*.py).

Prioritas path:
1. Environment variable (deployment / CI)
2. File .streamlit/secrets.toml (lokal)
3. Fallback default (mode demo offline)
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Path dasar
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PIPELINE_DIR = PROJECT_ROOT / "aws-svm-pejantan"
PLTS_PIPELINE_DIR = PROJECT_ROOT / "plts-svm-offgrid"

MODELS_DIR = PIPELINE_DIR / "models"
PLTS_MODELS_DIR = PLTS_PIPELINE_DIR / "models"
PLTS_LATEST_PREDICTION_JSON = PLTS_MODELS_DIR / "plts_latest_prediction.json"
PLTS_MODEL_META_JSON = PLTS_MODELS_DIR / "plts_model_meta.json"
PLTS_SVM_CLASSIFIER_PKL = PLTS_MODELS_DIR / "plts_svm_classifier.pkl"
PLTS_RAW_CSV = PLTS_PIPELINE_DIR / "data" / "ina226_records.csv"
DATA_DIR = PIPELINE_DIR / "data"

#: Pipeline SVM yang memakai data cuaca RIIL dari Visual Crossing.
VC_PIPELINE_DIR = PROJECT_ROOT / "aws-svm-pejantan-vc"
VC_MODELS_DIR = VC_PIPELINE_DIR / "models"
VC_LATEST_PREDICTION_JSON = VC_MODELS_DIR / "latest_prediction.json"
VC_MODEL_META_JSON = VC_MODELS_DIR / "model_meta.json"
VC_RAW_HISTORY_CSV = VC_PIPELINE_DIR / "data" / "raw_history.csv"

LATEST_PREDICTION_JSON = MODELS_DIR / "latest_prediction.json"
MODEL_META_JSON = MODELS_DIR / "model_meta.json"
SVM_CLASSIFIER_PKL = MODELS_DIR / "svm_classifier.pkl"
SVM_REGRESSOR_PKL = MODELS_DIR / "svm_regressor.pkl"
SCALER_PKL = MODELS_DIR / "scaler.pkl"
RAW_HISTORY_CSV = DATA_DIR / "raw_history.csv"
DATASET_CSV = DATA_DIR / "dataset_aws.csv"

# ---------------------------------------------------------------------------
# Firebase Realtime Database
# ---------------------------------------------------------------------------
#: Skema node yang dipakai ESP32 saat menulis data sensor mentah.
ESP32_RTDB_ROOT = "AWS_Monitoring"

#: Skema node yang dipakai pipeline Python (preprocess.py / config.py).
HISTORY_PATH_TEMPLATE = "aws_data/{station_id}/history"
PREDICTION_PATH_TEMPLATE = "predictions/{station_id}"

#: Fallback lokal untuk simulasi when Firebase tidak dapat diakses.
LOCAL_AUTH_DB = APP_DIR / ".auth_db.json"
LOCAL_STATIONS_DB = APP_DIR / ".stations.json"
LOCAL_PROFILE_DB = APP_DIR / ".profiles.json"

#: Batas ukuran berkas foto profil (byte) sebelum ditolak.
MAX_AVATAR_BYTES = 5 * 1024 * 1024
#: Sisi maksimum (piksel) foto profil yang disimpan.
AVATAR_MAX_DIMENSION = 256

# ---------------------------------------------------------------------------
# Daftar AWS (stasiun) yang dapat dimonitor
# ---------------------------------------------------------------------------
#: Metadata stasiun AWS. station_id dipakai sebagai kunci node di Firebase.
#: ID stasiun dapat ditambah/diubah di sini maupun melalui UI aplikasi.
DEFAULT_STATIONS = [
    {
        "station_id": "AWS_TPST_01",
        "nama": "AWS_TPST_01",
        "lokasi": "TPST Universitas Diponegoro, Semarang",
        "deskripsi": "Stasiun AWS Integrate cage ayam pejantan, sensor BME280/BH1750/INA226/GPS.",
        "objek": "Kandang Ayam Pejantan",
        "lat": -6.986,
        "lon": 110.375,
        "aktif": True,
    },
    {
        "station_id": "AWS_TPST_02",
        "nama": "AWS_TPST_02",
        "lokasi": "TPST Universitas Diponegoro, Semarang --areaKHRT-",
        "deskripsi": "Stasiun cadangan yang dapat diaktifkan saat deklarasi AWS baru.",
        "objek": "Kandang Ayam Pejantan",
        "lat": -6.9865,
        "lon": 110.3755,
        "aktif": False,
    },
    {
        "station_id": "AWS_TPST_VC",
        "nama": "AWS_TPST_VC",
        "lokasi": "TPST Universitas Diponegoro, Semarang (data Visual Crossing)",
        "deskripsi": (
            "Stasiun dengan data cuaca RIIL dari Visual Crossing Weather API, "
            "interval per jam, rentang 14 Agu 2026 - 14 Nov 2026. Dipakai sebagai "
            "bukti data lapangan dalam evaluasi model SVM."
        ),
        "objek": "Kandang Ayam Pejantan",
        "lat": -7.048,
        "lon": 110.435,
        "aktif": True,
    },
]

# ---------------------------------------------------------------------------
# Kredensial (opsional)
# ---------------------------------------------------------------------------
def _secret(name: str, default: str = "") -> str:
    """Ambil nilai secret dari environment variable atau st.secrets bila tersedia."""
    val = os.environ.get(name, "")
    if val:
        return val
    try:  # pragma: no cover - hanya berjalan di dalam runtime Streamlit
        import streamlit as st

        try:
            secret = st.secrets.get(name, default)
            if secret:
                return str(secret)
        except Exception:
            pass
    except Exception:
        pass
    return default


def get_firebase_db_url() -> str:
    """URL Firebase Realtime Database."""
    return _secret(
        "FIREBASE_DB_URL",
        "https://kandang-ayam-svm-default-rtdb.asia-southeast1.firebasedatabase.app/",
    )


def get_firebase_api_key() -> str:
    """Web API key Firebase Authentication (dipakai Identity Toolkit REST API)."""
    # Tanpa FIREBASE_API_KEY aplikasi berjalan dengan fallback autentikasi lokal.
    # Jangan menyimpan Web API key sebagai nilai default di repositori.
    return _secret("FIREBASE_API_KEY", "")


def get_firebase_project_id() -> str:
    return _secret("FIREBASE_PROJECT_ID", "kandang-ayam-svm")


def get_service_account_path() -> str:
    """Lokasi serviceAccountKey.json (opsional, untuk mode admin SDK)."""
    env = os.environ.get("FIREBASE_CREDENTIALS_PATH", "")
    if env and Path(env).exists():
        return env
    local = PIPELINE_DIR / "serviceAccountKey.json"
    if local.exists():
        return str(local)
    return ""


def get_firebase_credentials_json() -> str:
    """Isi JSON service account dari environment variable (opsional)."""
    return os.environ.get("FIREBASE_CREDENTIALS", "")


# ---------------------------------------------------------------------------
# Ambang batas domain (identik dengan config.py pada pipeline SVM)
# ---------------------------------------------------------------------------
SUHU_PANAS_WASPADA = 29.5
SUHU_PANAS_BAHAYA = 31.0
THI_WASPADA = 78.0
THI_BAHAYA = 82.0

#: Jumlah fitur masukan model SVM (6 dasar + 6 turunan temporal kausal).
FEATURE_COLS = [
    "suhu",
    "kelembapan",
    "tekanan",
    "cahaya",
    "hujan",
    "kecepatan_angin",
    "temp_change_1h",
    "humidity_change_1h",
    "pressure_change_1h",
    "rain_sum_3h",
    "temp_avg_3h",
    "humidity_avg_3h",
]

#: Variabel target yang diprediksi oleh Support Vector Regressor.
REGRESSION_TARGETS = ["suhu", "kelembapan", "kecepatan_angin", "hujan"]

# ---------------------------------------------------------------------------
# Pengaturan tampilan
# ---------------------------------------------------------------------------
APP_TITLE = "Coop Master"
APP_SUBTITLE = "Smart Poultry Microclimate & Solar Monitoring"
APP_ICON = "🐔"
WIB = "Asia/Jakarta"

AUTO_REFRESH_SECONDS = 60
HISTORY_LIMIT = 500
