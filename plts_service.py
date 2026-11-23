"""Pembacaan artefak pipeline PLTS SVM (INA226) untuk tampilan Streamlit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app_config import (
    PLTS_LATEST_PREDICTION_JSON,
    PLTS_MODEL_META_JSON,
    PLTS_RAW_CSV,
    PLTS_SVM_CLASSIFIER_PKL,
)

PLTS_CLASS_ICON = {
    "MALAM": "🌙",
    "NORMAL": "☀️",
    "IRADIASI_RENDAH": "🌥️",
    "PENURUNAN_DAYA": "⚠️",
    "CHARGING_DIBATASI": "🔋",
    "GANGGUAN": "🛑",
}

PLTS_CLASS_LEVEL = {
    "MALAM": "info",
    "NORMAL": "success",
    "IRADIASI_RENDAH": "warning",
    "PENURUNAN_DAYA": "danger",
    "CHARGING_DIBATASI": "info",
    "GANGGUAN": "danger",
}


def plts_models_available() -> Dict[str, bool]:
    return {
        "classifier": Path(PLTS_SVM_CLASSIFIER_PKL).exists(),
        "meta": Path(PLTS_MODEL_META_JSON).exists(),
        "prediction": Path(PLTS_LATEST_PREDICTION_JSON).exists(),
        "raw_csv": Path(PLTS_RAW_CSV).exists(),
    }


def load_plts_prediction() -> Optional[Dict[str, Any]]:
    path = Path(PLTS_LATEST_PREDICTION_JSON)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    cls = str(data.get("predicted_class", "-"))
    data["icon"] = PLTS_CLASS_ICON.get(cls, "⚡")
    data["level"] = PLTS_CLASS_LEVEL.get(cls, "info")
    return data


def load_plts_meta() -> Optional[Dict[str, Any]]:
    path = Path(PLTS_MODEL_META_JSON)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def plts_status_summary(payload: Optional[Dict[str, Any]]) -> str:
    if not payload:
        return "Data PLTS belum tersedia — jalankan pipeline plts-svm-offgrid."
    if payload.get("alarm"):
        return f"PERINGATAN: kondisi {payload.get('predicted_class', '-')} memerlukan tindakan."
    return f"Operasional normal — kelas {payload.get('predicted_class', '-')}"
