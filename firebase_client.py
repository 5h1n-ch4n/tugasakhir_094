"""
Lapisan akses data Firebase Realtime Database.

Menggunakan Firebase REST Database API (read-only via GET) sehingga aplikasi
dapat berjalan tanpa firebase-admin SDK. Bila kredensial admin tersedia,
ditawarkan mode admin SDK (write untuk registrasi stasiun & predicts).

Skema node yang didukung (dibaca otomatis):
  1. /AWS_Monitoring/terkini            -> data sensor ESP32 terkini
  2. /AWS_Monitoring/riwayat/<key>     -> riwayat sensor ESP32
  3. /aws_data/{station_id}/history    -> riwayat (pipeline Python)
  4. /predictions/{station_id}         -> hasil prediksi SVM
"""

from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_config import (
    ESP32_RTDB_ROOT,
    HISTORY_PATH_TEMPLATE,
    PREDICTION_PATH_TEMPLATE,
    RAW_HISTORY_CSV,
    VC_RAW_HISTORY_CSV,
    WIB,
    get_firebase_db_url,
    get_firebase_credentials_json,
    get_service_account_path,
)

WIB_OFFSET = timezone(timedelta(hours=7))

#: Admin SDK (firebase-admin) dipakai bila aturan keamanan Firebase menolak
#: permintaan anonim. Kredensial dibaca dari service account / env var.
try:
    import firebase_admin
    from firebase_admin import credentials as admin_credentials
    from firebase_admin import db as admin_db

    HAS_ADMIN_SDK = True
except ImportError:  # pragma: no cover - dependensi opsional
    firebase_admin = None
    admin_credentials = None
    admin_db = None
    HAS_ADMIN_SDK = False

#: Kunci sensor yang dibaca dari node ESP32 (dalam satuan aslinya).
ESP32_WEATHER_KEYS = {
    "suhu": ("cuaca/suhu_c", "cuaca/suhu"),
    "kelembapan": ("cuaca/kelembaban_persen", "cuaca/kelembapan_persen", "cuaca/kelembapan"),
    "tekanan": ("cuaca/tekanan_hpa", "cuaca/tekanan"),
    "cahaya": ("cuaca/cahaya_lux", "cuaca/cahaya"),
    "hujan": ("cuaca/hujan_interval_mm", "cuaca/hujan"),
    "kecepatan_angin": ("cuaca/angin_kmh", "cuaca/angin_ms"),
    "cloudcover": ("cloudcover", "cuaca/cloudcover", "cuaca/tutupan_awan_persen"),
}

ESP32_POWER_KEYS = {
    "tegangan_v": ("daya_ina226/tegangan_v",),
    "arus_ma": ("daya_ina226/arus_ma",),
    "daya_mw": ("daya_ina226/daya_mw",),
}

ESP32_GPS_KEYS = {
    "valid": ("gps/valid",),
    "latitude": ("gps/latitude",),
    "longitude": ("gps/longitude",),
    "altitude_m": ("gps/altitude_m",),
    "satelit": ("gps/satelit",),
}


# ---------------------------------------------------------------------------
# Utilitas
# ---------------------------------------------------------------------------
def _to_float(value: Any) -> Optional[float]:
    """Konversi aman ke float; mengembalikan None bila tidak valid."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result


def _dig(payload: Dict[str, Any], dotted: str) -> Any:
    """Ambil nilai dari dict dengan path bergaya titik (a/b/c)."""
    node: Any = payload
    for part in dotted.split("/"):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _pick(payload: Dict[str, Any], keys: List[str]) -> Optional[float]:
    """Ambil nilai numerik pertama yang ditemukan dari sekumpulan path."""
    for key in keys:
        value = _to_float(_dig(payload, key))
        if value is not None:
            return value
    return None


def _now_wib() -> datetime:
    return datetime.now(WIB_OFFSET)


# ---------------------------------------------------------------------------
# Klien REST
# ---------------------------------------------------------------------------
class FirebaseRestClient:
    """Klien ringan untuk Firebase Realtime Database via REST API.

    Mendukung dua mode akses:
      * Anonim (REST GET) -- dipakai bila aturan keamanan Firebase mengizinkan.
      * Admin SDK -- dipakai bila aturan keamanan menolak permintaan anonim
        (kondisi umum pada Realtime Database dengan autentikasi aktif).
    """

    def __init__(self, base_url: Optional[str] = None, timeout: int = 12):
        self.base_url = (base_url or get_firebase_db_url()).rstrip("/")
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self._admin_ready: Optional[bool] = None

    # -- utilitas internal --------------------------------------------------
    def _ensure_admin(self) -> bool:
        """Inisialisasi Firebase Admin SDK bila kredensial tersedia."""
        if self._admin_ready is not None:
            return self._admin_ready

        self._admin_ready = False
        if not HAS_ADMIN_SDK:
            return False

        try:
            if not firebase_admin._apps:
                cred_json = get_firebase_credentials_json()
                if cred_json:
                    cred = admin_credentials.Certificate(json.loads(cred_json))
                else:
                    path = get_service_account_path()
                    if not path:
                        return False
                    cred = admin_credentials.Certificate(path)
                firebase_admin.initialize_app(
                    cred, {"databaseURL": self.base_url}
                )
            self._admin_ready = True
        except Exception as exc:  # pragma: no cover - kredensial tidak valid
            self.last_error = f"Admin SDK tidak aktif: {exc}"
            self._admin_ready = False
        return self._admin_ready

    @property
    def using_admin_sdk(self) -> bool:
        """True bila akses memakai Firebase Admin SDK."""
        return bool(self._admin_ready)

    def _admin_get(self, path: str) -> Optional[Any]:
        """Baca node melalui Admin SDK."""
        try:
            reference = admin_db.reference(path)
            return reference.get()
        except Exception as exc:  # pragma: no cover - jaringan
            self.last_error = f"Gagal membaca via Admin SDK: {exc}"
            return None

    def _request(self, method: str, path: str, payload: Any = None) -> Optional[Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        url += ".json" if not url.endswith(".json") else ""
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                self.last_error = None
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="ignore")[:200]
            except Exception:
                pass
            self.last_error = f"HTTP {exc.code}: {detail}"
            return None
        except urllib.error.URLError as exc:
            self.last_error = f"Gagal koneksi: {exc.reason}"
            return None
        except (TimeoutError, json.JSONDecodeError, OSError) as exc:
            self.last_error = f"Gagal membaca Firebase: {exc}"
            return None

    # -- API publik ---------------------------------------------------------
    def get(self, path: str) -> Optional[Any]:
        """Baca satu node. Mengembalikan None bila tidak ada / gagal.

        Urutan percobaan: Admin SDK (bila aktif) -> REST anonim.
        """
        if self._ensure_admin():
            value = self._admin_get(path)
            if value is not None:
                self.last_error = None
                return value

        return self._request("GET", path)

    def get_history(self, path: str, limit: int = 200) -> List[Dict[str, Any]]:
        """Baca node riwayat lalu urutkan berdasarkan kunci."""
        raw = self.get(path)
        if not isinstance(raw, dict) or not raw:
            return []
        items = []
        for key, value in raw.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry["_key"] = key
                items.append(entry)
        items.sort(key=lambda item: _sort_key(item))
        return items[-limit:]

    def set(self, path: str, value: Any) -> bool:
        """Tulis nilai ke node (hanya dipakai bila admin SDK tidak tersedia)."""
        result = self._request("PUT", path, value)
        return result is not None


def _sort_key(entry: Dict[str, Any]) -> str:
    """Kunci pengurutan kronologis dari timestamp atau push key."""
    ts = entry.get("timestamp")
    number = _to_float(ts)
    if number is not None:
        return f"{number:020.0f}"
    return str(entry.get("_key", ""))


# ---------------------------------------------------------------------------
# Normalisasi data sensor
# ---------------------------------------------------------------------------
def normalize_sensor_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Ubah payload mentah (ESP32 atau pipeline) menjadi format seragam.

    Kunci keluaran: suhu, kelembapan, tekanan, cahaya, hujan, kecepatan_angin,
    tegangan_v, arus_ma, daya_mw, latitude, longitude, altitude_m, satelit,
    timestamp (epoch ms), waktu (string WIB).
    """
    weather = record.get("cuaca") if isinstance(record.get("cuaca"), dict) else record

    def pick(keys: List[str]) -> Optional[float]:
        """Ambil nilai numerik dari node cuaca, lalu node daya, lalu node GPS, lalu akar."""
        scopes = [weather, record]
        for scope in scopes:
            for key in keys:
                value = _to_float(_dig(scope, key))
                if value is not None:
                    return value
        # Node daya & GPS berada di luar objek "cuaca".
        for group in ("daya_ina226", "gps"):
            section = record.get(group)
            if not isinstance(section, dict):
                continue
            for key in keys:
                value = _to_float(section.get(key))
                if value is not None:
                    return value
        return None

    # Kecepatan angin: ESP32 menyimpan m/s dan km/h, pipeline memakai
    # key Bahasa Indonesia "kecepatan_angin" (satuan km/j).
    wind_kmh = _to_float(_dig(weather, "angin_kmh"))
    if wind_kmh is None:
        wind_kmh = _to_float(_dig(weather, "kecepatan_angin"))
    if wind_kmh is None:
        wind_kmh = _to_float(_dig(weather, "angin_ms"))
        if wind_kmh is not None:
            wind_kmh = round(wind_kmh * 3.6, 2)

    humidity = pick(["kelembaban_persen", "kelembapan_persen", "kelembapan"])
    # Pipeline Python memakai satuan persen, ESP32 juga persen -> konsisten.

    ts_ms = _to_float(record.get("timestamp"))
    waktu = record.get("waktu") or record.get("time")
    if ts_ms is None:
        ts_ms = _to_float(record.get("ts"))
    if ts_ms is not None and ts_ms < 1e11:
        ts_ms *= 1000.0
    if ts_ms is None and isinstance(waktu, str) and waktu:
        try:
            parsed = datetime.strptime(waktu[:19], "%Y-%m-%d %H:%M:%S")
            ts_ms = parsed.replace(tzinfo=WIB_OFFSET).timestamp() * 1000.0
        except ValueError:
            ts_ms = None
    if ts_ms is None:
        ts_ms = _now_wib().timestamp() * 1000.0

    return {
        "suhu": pick(["suhu_c", "suhu", "temperature"]),
        "kelembapan": humidity,
        "tekanan": pick(["tekanan_hpa", "tekanan", "pressure"]),
        "cahaya": pick(["cahaya_lux", "cahaya", "light"]),
        "hujan": pick(["hujan_interval_mm", "hujan", "rain"]),
        "kecepatan_angin": wind_kmh,
        "cloudcover": pick(["cloudcover", "cloudcover_persen", "tutupan_awan_persen"]),
        "tegangan_v": pick(["tegangan_v", "voltage"]),
        "arus_ma": pick(["arus_ma", "current"]),
        "daya_mw": pick(["daya_mw", "power"]),
        "latitude": pick(["latitude", "lat"]),
        "longitude": pick(["longitude", "lon", "lng"]),
        "altitude_m": pick(["altitude_m", "altitude"]),
        "satelit": pick(["satelit", "satellites"]),
        "timestamp": ts_ms,
        "waktu": _format_wib(ts_ms, waktu),
        "_key": record.get("_key", ""),
    }


def _format_wib(ts_ms: float, fallback: Optional[str] = None) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=WIB_OFFSET).strftime(
            "%Y-%m-%d %H:%M:%S WIB"
        )
    except (ValueError, OSError, OverflowError):
        return fallback or "-"


# ---------------------------------------------------------------------------
# Pembaca data per stasiun
# ---------------------------------------------------------------------------
def read_latest_sensor(client: FirebaseRestClient, station_id: str) -> Dict[str, Any]:
    """Baca data sensor terkini untuk sebuah stasiun.

    Prioritas: node per-stasiun (pipeline) > node global ESP32.
    """
    candidates = [
        f"{HISTORY_PATH_TEMPLATE.format(station_id=station_id)}",
        f"{ESP32_RTDB_ROOT}/terkini",
    ]
    for path in candidates:
        raw = client.get(path)
        if not isinstance(raw, dict) or not raw:
            continue

        if path.endswith("/history"):
            entries = [
                {"_key": key, **value}
                for key, value in raw.items()
                if isinstance(value, dict)
            ]
            if not entries:
                continue
            entries.sort(key=lambda item: _sort_key(item))
            raw = entries[-1]
        elif path.endswith("/terkini"):
            raw = {**raw, "_key": "terkini"}

        if not any(key in raw for key in ("cuaca", "suhu", "suhu_c")):
            continue
        return normalize_sensor_record(raw)
    return {}


def _read_local_history_csv(station_id: str, limit: int) -> List[Dict[str, Any]]:
    """Baca riwayat dari CSV lokal pipeline bila Firebase tidak tersedia.

    Untuk stasiun Visual Crossing (AWS_TPST_VC) sumbernya adalah
    `aws-svm-pejantan-vc/data/raw_history.csv`, untuk stasiun simulasi adalah
    `aws-svm-pejantan/data/raw_history.csv`. CSV lokal berisi kolom Bahasa
    Indonesia sehingga harus dipetakan ke skema `cuaca/*` sebelum dinormalisasi.
    """
    import csv

    if station_id == "AWS_TPST_VC":
        csv_path = VC_RAW_HISTORY_CSV
    else:
        csv_path = RAW_HISTORY_CSV

    path = Path(csv_path)
    if not path.exists():
        return []

    entries: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                try:
                    entries.append(
                        {
                            "timestamp": int(float(row["timestamp"])),
                            "kondisi_cuaca": row.get("kondisi_cuaca", ""),
                            "cloudcover": float(row.get("cloudcover") or 0.0),
                            "cuaca": {
                                "suhu_c": float(row["suhu"]),
                                "kelembapan_persen": float(row["kelembapan"]),
                                "tekanan_hpa": float(row["tekanan"]),
                                "cahaya_lux": float(row["cahaya"]),
                                "hujan_interval_mm": float(row["hujan"]),
                                "angin_kmh": float(row["kecepatan_angin"]),
                            },
                        }
                    )
                except (KeyError, ValueError, TypeError):
                    continue
    except OSError:
        return []

    entries.sort(key=_sort_key)
    return entries[-limit:]


def read_sensor_history(
    client: FirebaseRestClient, station_id: str, limit: int = 200
) -> List[Dict[str, Any]]:
    """Baca riwayat sensor dan normalisasi tiap rekaman."""
    raw_entries: List[Dict[str, Any]] = []
    for path in (
        f"{HISTORY_PATH_TEMPLATE.format(station_id=station_id)}",
        f"{ESP32_RTDB_ROOT}/riwayat",
    ):
        raw_entries = client.get_history(path, limit=limit)
        if raw_entries:
            break

    if not raw_entries:
        raw_entries = _read_local_history_csv(station_id, limit)

    normalized: List[Dict[str, Any]] = []
    for entry in raw_entries:
        record = normalize_sensor_record(entry)
        if record.get("suhu") is None and record.get("kelembapan") is None:
            continue
        normalized.append(record)
    return normalized


def read_prediction(
    client: FirebaseRestClient, station_id: str
) -> Optional[Dict[str, Any]]:
    """Baca hasil prediksi SVM dari Firebase."""
    raw = client.get(PREDICTION_PATH_TEMPLATE.format(station_id=station_id))
    if isinstance(raw, dict) and raw:
        return raw
    return None


def read_available_stations(client: FirebaseRestClient) -> List[str]:
    """Deteksi daftar stasiun yang tersedia di Firebase."""
    found: List[str] = []
    raw = client.get("aws_data")
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(value, dict) and "history" in value:
                found.append(key)
    return sorted(found)
