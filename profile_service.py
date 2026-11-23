"""
Penyimpanan profil pengguna (nama, foto, tempat & tanggal lahir).

Profil disimpan pada berkas JSON lokal di folder aplikasi sehingga dapat
diubah dari antarmuka pengguna tanpa menyentuh pipeline yang sudah berjalan.
Data bersifat non-sensitif (tidak memuat kata sandi atau token), sehingga aman
disimpan di samping tabel akun lokal.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app_config import AVATAR_MAX_DIMENSION, LOCAL_PROFILE_DB, MAX_AVATAR_BYTES

WIB_OFFSET = timezone(timedelta(hours=7))

#: Field profil yang boleh disimpan.
PROFILE_FIELDS = ("full_name", "display_name", "birth_place", "birth_date", "photo_b64")

#: Warna lencana avatar (dipilih berdasar inisial agar konsisten).
AVATAR_PALETTE = [
    "#0f766e",
    "#1f6f43",
    "#0369a1",
    "#7c3aed",
    "#b45309",
    "#be123c",
    "#0e7490",
    "#4d7c0f",
]


# ---------------------------------------------------------------------------
# Penyimpanan
# ---------------------------------------------------------------------------
def _load_db() -> Dict[str, Any]:
    path = Path(LOCAL_PROFILE_DB)
    if not path.exists():
        return {"profiles": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"profiles": {}}
    if not isinstance(data, dict):
        return {"profiles": {}}
    data.setdefault("profiles", {})
    return data


def _save_db(data: Dict[str, Any]) -> None:
    path = Path(LOCAL_PROFILE_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def default_profile(email: str = "", display_name: str = "") -> Dict[str, Any]:
    """Profil kosong dengan nilai awal dari akun."""
    name = (display_name or (email or "").split("@")[0] or "Pengguna").strip()
    return {
        "email": (email or "").strip().lower(),
        "full_name": name,
        "display_name": name,
        "birth_place": "",
        "birth_date": "",
        "photo_b64": "",
        "created_at": datetime.now(WIB_OFFSET).isoformat(),
        "updated_at": datetime.now(WIB_OFFSET).isoformat(),
    }


def load_profile(email: str, display_name: str = "") -> Dict[str, Any]:
    """Ambil profil pengguna; bila belum pernah disimpan memakai nilai bawaan."""
    email = (email or "").strip().lower()
    profile = _load_db()["profiles"].get(email)
    if not isinstance(profile, dict):
        return default_profile(email, display_name)
    merged = default_profile(email, display_name)
    merged.update({key: profile.get(key, merged[key]) for key in PROFILE_FIELDS})
    merged["created_at"] = profile.get("created_at", merged["created_at"])
    merged["updated_at"] = profile.get("updated_at", merged["updated_at"])
    if not merged.get("display_name"):
        merged["display_name"] = merged.get("full_name") or display_name or "Pengguna"
    return merged


def save_profile(email: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    """Simpan perubahan profil dan kembalikan profil terbaru."""
    email = (email or "").strip().lower()
    if not email:
        raise ValueError("Surel profil wajib diisi.")

    data = _load_db()
    profiles = data["profiles"]
    current = profiles.get(email) or default_profile(email)
    for key in PROFILE_FIELDS:
        if key in updates:
            current[key] = updates[key]
    current["email"] = email
    current["updated_at"] = datetime.now(WIB_OFFSET).isoformat()
    current.setdefault("created_at", current["updated_at"])
    profiles[email] = current
    _save_db(data)
    return current


def clear_photo(email: str) -> Dict[str, Any]:
    """Hapus foto profil yang tersimpan."""
    return save_profile(email, {"photo_b64": ""})


# ---------------------------------------------------------------------------
# Helper tampilan
# ---------------------------------------------------------------------------
def initials(name: str, fallback: str = "?") -> str:
    """Ambil inisial (maksimal 2 huruf) dari sebuah nama.

    Contoh: "Haikal Karim" -> "HK"; "haikal" -> "H".
    """
    parts = [part for part in (name or "").replace(".", " ").split() if part]
    if not parts:
        return fallback
    if len(parts) == 1:
        return parts[0][:1].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()


def avatar_color(name: str) -> str:
    """Pilih warna lencana avatar secara deterministik berdasar nama."""
    key = (name or "?").strip().lower()
    if not key:
        return AVATAR_PALETTE[0]
    total = sum(ord(char) for char in key)
    return AVATAR_PALETTE[total % len(AVATAR_PALETTE)]


def decode_photo(photo_b64: str) -> Optional[bytes]:
    """Ubah data base64 foto menjadi byte gambar."""
    if not photo_b64:
        return None
    try:
        return base64.b64decode(photo_b64)
    except (ValueError, TypeError):
        return None


def encode_photo(raw: bytes) -> Tuple[str, Optional[str]]:
    """Kompres gambar menjadi string base64.

    Mengembalikan (base64, pesan_galat). Bila Pillow terpasang, gambar
    diperkecil menjadibujur/tinggi maksimal 256 piksel dan disimpan sebagai
    JPEG sehingga berkas profil tetap ringan.
    """
    if not raw:
        return "", "Berkas gambar kosong."
    if len(raw) > MAX_AVATAR_BYTES:
        return "", "Ukuran gambar melebihi 5 MB. Pilih gambar yang lebih kecil."

    try:
        import io

        from PIL import Image

        image = Image.open(io.BytesIO(raw))
        image = image.convert("RGB")
        image.thumbnail((AVATAR_MAX_DIMENSION, AVATAR_MAX_DIMENSION))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("ascii"), None
    except ImportError:
        # Tanpa Pillow: simpan mentah asalkan tetap di bawah 1,5 MB.
        if len(raw) > 1_500_000:
            return "", "Pasang Pillow (pip install Pillow) untuk foto berukuran besar."
        return base64.b64encode(raw).decode("ascii"), None
    except Exception as exc:  # pragma: no cover - berkas rusak
        return "", f"Gambar tidak dapat diproses: {exc}"


def age_from_birth_date(birth_date: str) -> Optional[int]:
    """Hitung usia dari tanggal lahir (format YYYY-MM-DD)."""
    if not birth_date:
        return None
    try:
        born = datetime.strptime(str(birth_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now(WIB_OFFSET).date()
    if born > today:
        return None
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def profile_summary(profile: Dict[str, Any]) -> str:
    """Ringkasan satu baris untuk sidebar."""
    parts: list[str] = []
    place = str(profile.get("birth_place", "")).strip()
    if place:
        parts.append(place)
    age = age_from_birth_date(str(profile.get("birth_date", "")))
    if age is not None:
        parts.append(f"{age} tahun")
    return " • ".join(parts)
