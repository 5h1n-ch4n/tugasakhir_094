"""
Modul data & perhitungan domain.

Mengambil hasil prediksi SVM (dari Firebase atau berkas lokal
models/latest_prediction.json), menghitung THI, dan menyusun status
stres panas serta rekomendasi kipas untuk ayam pejantan.

Modul ini sengaja TIDAK mengimpor modul di folder aws-svm-pejantan secara
langsung agar aplikasi tetap berjalan meski pipeline berada di lokasi lain.
Formula THI disalin sesuai standar NRC/Thom yang dipakai pada pipeline.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_config import (
    LATEST_PREDICTION_JSON,
    MODEL_META_JSON,
    SVM_CLASSIFIER_PKL,
    SVM_REGRESSOR_PKL,
    VC_LATEST_PREDICTION_JSON,
)

WIB_OFFSET = timezone(timedelta(hours=7))

#: Ambang batas domain (identik dengan config.py pada pipeline).
SUHU_PANAS_WASPADA = 29.5
SUHU_PANAS_BAHAYA = 31.0
THI_WASPADA = 78.0
THI_BAHAYA = 82.0

WEATHER_ICONS = {
    "Cerah": "☀️",
    "Berawan": "⛅",
    "Berang-berang": "☁️",
    "Hujan Ringan": "🌦️",
    "Hujan Lebat": "🌧️",
}


# ---------------------------------------------------------------------------
# THI & rekomendasi
# ---------------------------------------------------------------------------
def _to_number(value: Any) -> Optional[float]:
    """Ubah nilai apa pun menjadi float, atau None bila tidak valid."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def calculate_thi(temp_c: Any, rh_pct: Any) -> float:
    """Hitung Temperature-Humidity Index (THI) standar NRC/Thom.

    Nilai masukan yang tidak valid (None, string non-numerik, NaN) akan
    menghasilkan nilai 0.0 sehingga tidak menyebabkan galat saat tampil.
    """
    temp = _to_number(temp_c)
    rh = _to_number(rh_pct)
    if temp is None or rh is None:
        return 0.0
    t_f = 1.8 * temp + 32.0
    thi = t_f - ((0.55 - 0.0055 * rh) * (1.8 * temp - 26.0))
    return round(float(thi), 2)


def evaluate_heat_stress(suhu: Any, kelembapan: Any) -> Dict[str, Any]:
    """Nilai status stres panas dari suhu dan kelembapan.

    Mengembalikan dict berisi thi, status, level, dan rekomendasi kipas.
    """
    suhu = _to_number(suhu)
    kelembapan = _to_number(kelembapan)
    if suhu is None or kelembapan is None:
        return {
            "thi": None,
            "status": "DATA TIDAK TERSEDIA",
            "level": "unknown",
            "fan": "-",
            "warna": "#6b7280",
            "pesan": "Data sensor tidak lengkap sehingga THI tidak dapat dihitung.",
        }

    thi = calculate_thi(suhu, kelembapan)
    if suhu >= SUHU_PANAS_BAHAYA or thi >= THI_BAHAYA:
        return {
            "thi": thi,
            "status": "BAHAYA STRES PANAS",
            "level": "danger",
            "fan": "NYALAKAN KIPAS PENUH (100%)",
            "warna": "#dc2626",
            "pesan": (
                f"Suhu {suhu:.1f}°C dengan THI {thi} berada pada zona bahaya. "
                "Ayam pejantan berisiko stres panas dan mogok makan. "
                "Segera nyalakan seluruh kipas exhaust/blower dan pastikan air minum lancar."
            ),
        }
    if suhu >= SUHU_PANAS_WASPADA or thi >= THI_WASPADA:
        return {
            "thi": thi,
            "status": "WASPADA PANAS",
            "level": "warning",
            "fan": "NYALAKAN KIPAS SEDANG (50-75%)",
            "warna": "#f59e0b",
            "pesan": (
                f"Suhu {suhu:.1f}°C dengan THI {thi} mulai masuk zona waspada. "
                "Nyalakan kipas sirkulasi agar suhu kandang tetap adem dan nafsu makan terjaga."
            ),
        }
    return {
        "thi": thi,
        "status": "NYAMAN (AMAN)",
        "level": "success",
        "fan": "VENTILASI NORMAL / MINIMAL",
        "warna": "#16a34a",
        "pesan": (
            f"Suhu {suhu:.1f}°C dengan THI {thi} berada pada zona nyaman. "
            "Ayam pejantan tahan suhu dingin sehingga tidak diperlukan pemanas. "
            "Kipas cukup pada mode sirkulasi normal."
        ),
    }


# ---------------------------------------------------------------------------
# Pembacaan hasil prediksi
# ---------------------------------------------------------------------------
def load_local_prediction(station_id: str = "") -> Optional[Dict[str, Any]]:
    """Baca models/latest_prediction.json dari pipeline Python (bila ada).

    Untuk stasiun `AWS_TPST_VC` (data riil Visual Crossing) sumbernya adalah
    folder pipeline `aws-svm-pejantan-vc`, sedangkan stasiun lain memakai
    pipeline simulasi `aws-svm-pejantan`.
    """
    if station_id == "AWS_TPST_VC":
        path = Path(VC_LATEST_PREDICTION_JSON)
    else:
        path = Path(LATEST_PREDICTION_JSON)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def load_prediction_for_station(client, station_id: str) -> Optional[Dict[str, Any]]:
    """Ambil prediksi terbaru: cloud dulu, lalu berkas lokal (tanpa UI mengekspos sumber)."""
    import firebase_client as _fb

    remote = _fb.read_prediction(client, station_id)
    if remote:
        return remote
    return load_local_prediction(station_id)


def load_model_meta() -> Optional[Dict[str, Any]]:
    """Baca models/model_meta.json dari pipeline Python (bila ada)."""
    path = Path(MODEL_META_JSON)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def models_available() -> Dict[str, bool]:
    """Periksa keberadaan berkas model SVM hasil pelatihan."""
    return {
        "classifier": Path(SVM_CLASSIFIER_PKL).exists(),
        "regressor": Path(SVM_REGRESSOR_PKL).exists(),
        "meta": Path(MODEL_META_JSON).exists(),
        "prediction": Path(LATEST_PREDICTION_JSON).exists(),
    }


def normalize_prediction(payload: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Normalisasi payload prediksi menjadi struktur yang seragam."""
    if not payload or not isinstance(payload, dict):
        return None

    forecast = payload.get("forecast_values") or payload.get("forecast") or {}
    if not isinstance(forecast, dict):
        forecast = {}

    def num(key: str, default: Optional[float] = None) -> Optional[float]:
        value = forecast.get(key, payload.get(key, default))
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    pred_class = str(payload.get("predicted_class") or payload.get("kelas") or "-")
    probabilities = payload.get("probabilities_pct") or {}
    if not isinstance(probabilities, dict):
        probabilities = {}

    suhu = num("suhu")
    kelembapan = num("kelembapan")
    heat = evaluate_heat_stress(suhu, kelembapan)

    # Gunakan THI dari pipeline bila tersedia (authoritative).
    thi_remote = payload.get("thi_forecast")
    if thi_remote is not None:
        try:
            heat["thi"] = round(float(thi_remote), 2)
        except (TypeError, ValueError):
            pass

    return {
        "station_id": payload.get("station_id", "-"),
        "object_type": payload.get("object_type", "-"),
        "observation_time": payload.get("observation_time", "-"),
        "forecast_time": payload.get("forecast_time", "-"),
        "predicted_class": pred_class,
        "icon": WEATHER_ICONS.get(pred_class, "🌡️"),
        "probabilities_pct": {str(k): float(v) for k, v in probabilities.items()},
        "forecast": {
            "suhu": suhu,
            "kelembapan": kelembapan,
            "kecepatan_angin": num("kecepatan_angin"),
            "hujan": num("hujan"),
            "tekanan": num("tekanan"),
            "cahaya": num("cahaya"),
        },
        "thi_forecast": heat["thi"],
        "heat_stress_status": payload.get("heat_stress_status", heat["status"]),
        "fan_recommendation": payload.get("fan_recommendation", heat["fan"]),
        "recommendations": payload.get("recommendations") or [heat["pesan"]],
        "level": heat["level"],
        "warna": heat["warna"],
    }


def predict_from_model(features: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """Jalankan inferensi SVM lokal memakai model yang sudah dilatih.

    Berguna bila Firebase tidak dapat dijangkau tetapi berkas model tersedia.
    """
    if not Path(SVM_CLASSIFIER_PKL).exists() or not Path(SVM_REGRESSOR_PKL).exists():
        return None
    try:
        import joblib
        import numpy as np
    except ImportError:
        return None

    try:
        classifier = joblib.load(SVM_CLASSIFIER_PKL)
        regressors = joblib.load(SVM_REGRESSOR_PKL)
        meta = load_model_meta() or {}
    except Exception:
        return None

    feature_cols = meta.get("features") or []
    if not feature_cols:
        return None

    vector = np.array([[float(features.get(col, 0.0)) for col in feature_cols]])
    try:
        pred_class = str(classifier.predict(vector)[0])
        probabilities = {
            str(cls): round(float(prob) * 100.0, 2)
            for cls, prob in zip(classifier.classes_, classifier.predict_proba(vector)[0])
        }
        bounds = meta.get("train_bounds", {})
        forecast: Dict[str, float] = {}
        for target, model in regressors.items():
            value = float(model.predict(vector)[0])
            if target in bounds:
                value = float(
                    np.clip(value, bounds[target]["min"], bounds[target]["max"])
                )
            forecast[target] = round(value, 2)
    except Exception:
        return None

    now = datetime.now(WIB_OFFSET)
    return normalize_prediction(
        {
            "station_id": "AWS_TPST_01",
            "object_type": "Kandang Ayam Pejantan",
            "observation_time": now.strftime("%Y-%m-%d %H:%M:%S WIB"),
            "forecast_time": (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S WIB"),
            "predicted_class": pred_class,
            "probabilities_pct": probabilities,
            "forecast_values": forecast,
        }
    )


# ---------------------------------------------------------------------------
# Pengolahan riwayat untuk grafik
# ---------------------------------------------------------------------------
def history_to_series(history: List[Dict[str, Any]]) -> Dict[str, List[Any]]:
    """Ubah daftar riwayat sensor menjadi struktur siap grafik."""
    series: Dict[str, List[Any]] = {
        "waktu": [],
        "suhu": [],
        "kelembapan": [],
        "hujan": [],
        "kecepatan_angin": [],
        "thi": [],
    }
    for record in history:
        series["waktu"].append(record.get("waktu", ""))
        series["suhu"].append(record.get("suhu"))
        series["kelembapan"].append(record.get("kelembapan"))
        series["hujan"].append(record.get("hujan"))
        series["kecepatan_angin"].append(record.get("kecepatan_angin"))
        suhu = record.get("suhu")
        lembap = record.get("kelembapan")
        series["thi"].append(
            calculate_thi(suhu, lembap) if suhu is not None and lembap is not None else None
        )
    return series


def summarize_current(sensor: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan cuaca saat ini dari data sensor terkini."""
    if not sensor:
        return {}

    suhu = sensor.get("suhu")
    lembap = sensor.get("kelembapan")
    heat = evaluate_heat_stress(suhu, lembap)

    return {
        "waktu": sensor.get("waktu", "-"),
        "suhu": suhu,
        "kelembapan": lembap,
        "tekanan": sensor.get("tekanan"),
        "cahaya": sensor.get("cahaya"),
        "hujan": sensor.get("hujan"),
        "kecepatan_angin": sensor.get("kecepatan_angin"),
        "thi": heat["thi"],
        "heat_status": heat["status"],
        "level": heat["level"],
        "warna": heat["warna"],
        "tegangan_v": sensor.get("tegangan_v"),
        "arus_ma": sensor.get("arus_ma"),
        "daya_mw": sensor.get("daya_mw"),
        "latitude": sensor.get("latitude"),
        "longitude": sensor.get("longitude"),
        "altitude_m": sensor.get("altitude_m"),
        "satelit": sensor.get("satelit"),
    }
