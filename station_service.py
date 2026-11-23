"""
Manajemen stasiun AWS (multi-AWS monitoring).

Stasiun disimpan pada file .stations.json di folder aplikasi sehingga dapat
diubah dari antarmuka pengguna tanpa menyentuh folder pipeline yang sudah ada.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from app_config import DEFAULT_STATIONS, LOCAL_STATIONS_DB

WIB_OFFSET = timezone(timedelta(hours=7))


def _default_payload() -> List[Dict[str, Any]]:
    return [dict(station) for station in DEFAULT_STATIONS]


def load_stations() -> List[Dict[str, Any]]:
    """Baca daftar stasiun; bila berkas belum ada gunakan daftar bawaan."""
    path = Path(LOCAL_STATIONS_DB)
    if not path.exists():
        stations = _default_payload()
        save_stations(stations)
        return stations
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return _default_payload()
    if not isinstance(data, list) or not data:
        return _default_payload()
    return data


def save_stations(stations: List[Dict[str, Any]]) -> None:
    """Simpan daftar stasiun ke berkas JSON lokal."""
    path = Path(LOCAL_STATIONS_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(stations, handle, indent=2, ensure_ascii=False)


def find_station(stations: List[Dict[str, Any]], station_id: str) -> Dict[str, Any]:
    """Cari stasiun berdasarkan station_id."""
    for station in stations:
        if station.get("station_id") == station_id:
            return station
    return {}


def upsert_station(station: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tambahkan atau perbarui stasiun; mengembalikan daftar terbaru."""
    stations = load_stations()
    station_id = str(station.get("station_id", "")).strip()
    if not station_id:
        raise ValueError("station_id wajib diisi.")
    station = dict(station)
    station["station_id"] = station_id
    station.setdefault("nama", station_id)
    station.setdefault("lokasi", "-")
    station.setdefault("deskripsi", "-")
    station.setdefault("objek", "Kandang Ayam Pejantan")
    station.setdefault("lat", None)
    station.setdefault("lon", None)
    station.setdefault("aktif", True)
    station["updated_at"] = datetime.now(WIB_OFFSET).isoformat()

    for index, existing in enumerate(stations):
        if existing.get("station_id") == station_id:
            stations[index] = station
            break
    else:
        stations.append(station)
    save_stations(stations)
    return stations


def delete_station(station_id: str) -> List[Dict[str, Any]]:
    """Hapus stasiun berdasarkan station_id."""
    stations = [item for item in load_stations() if item.get("station_id") != station_id]
    save_stations(stations)
    return stations


def toggle_station(station_id: str) -> List[Dict[str, Any]]:
    """Alihkan status aktif/nonaktif sebuah stasiun."""
    stations = load_stations()
    for station in stations:
        if station.get("station_id") == station_id:
            station["aktif"] = not station.get("aktif", True)
            station["updated_at"] = datetime.now(WIB_OFFSET).isoformat()
    save_stations(stations)
    return stations


def active_stations() -> List[Dict[str, Any]]:
    """Daftar stasiun yang berstatus aktif."""
    return [station for station in load_stations() if station.get("aktif", True)]


def station_select_label(station: Dict[str, Any]) -> str:
    """Teks tampilan stasiun untuk selectbox (tanpa menampilkan kode teknis)."""
    nama = (station.get("nama") or station.get("station_id") or "Stasiun").strip()
    lokasi = (station.get("lokasi") or "").strip()
    if lokasi and lokasi not in ("-", nama):
        return f"{nama} — {lokasi}"
    return nama


def station_label_map(stations: List[Dict[str, Any]]) -> Dict[str, str]:
    """Peta station_id -> label tampilan untuk format_func selectbox."""
    return {s["station_id"]: station_select_label(s) for s in stations if s.get("station_id")}
