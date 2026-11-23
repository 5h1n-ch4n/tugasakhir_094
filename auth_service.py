"""
Modul autentikasi pengguna.

Dua mode yang didukung:

1. MODE FIREBASE (utama)
   Menggunakan Firebase Authentication - Identity Toolkit REST API
   (signUp, signInWithPassword, sendOobCode untuk lupa password).
   Tidak memerlukan firebase-admin SDK, cukup Web API key.

2. MODE LOKAL (fallback / offline)
   Menyimpan akun pada file JSON lokal dengan hash PBKDF2-HMAC-SHA256.
   Dipakai ketika Firebase tidak dapat dijangkau (mis. pada saat pengujian
   blackbox di jaringan tanpa akses internet).

Sesi pengguna disimpan pada session state Streamlit, bukan pada cookie.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app_config import (
    LOCAL_AUTH_DB,
    get_firebase_api_key,
    get_firebase_db_url,
)

WIB_OFFSET = timezone(timedelta(hours=7))

#: Jumlah iterasi PBKDF2 untuk penyimpanan lokal.
PBKDF2_ITERATIONS = 120_000

#: Masa berlaku token reset password (menyesuaikan default Firebase).
RESET_TOKEN_TTL_MINUTES = 60


class AuthError(Exception):
    """Kesalahan autentikasi yang aman ditampilkan ke pengguna."""


# ---------------------------------------------------------------------------
# Utilitas kata sandi (mode lokal)
# ---------------------------------------------------------------------------
def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    """Buat hash PBKDF2-HMAC-SHA256 berformat 'salt$hash' (base64)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, stored: str) -> bool:
    """Verifikasi kata sandi terhadap hash tersimpan dengan perbandingan konstan."""
    try:
        salt_b64, hash_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(derived, expected)


def validate_password_strength(password: str) -> Optional[str]:
    """Periksa kekuatan kata sandi. Mengembalikan pesan galat atau None."""
    if len(password) < 6:
        return "Kata sandi minimal 6 karakter."
    if not any(ch.isalpha() for ch in password):
        return "Kata sandi harus memuat minimal satu huruf."
    if not any(ch.isdigit() for ch in password):
        return "Kata sandi harus memuat minimal satu angka."
    return None


def validate_email(email: str) -> Optional[str]:
    """Periksa format surel sederhana."""
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return "Format surel tidak valid."
    return None


# ---------------------------------------------------------------------------
# Penyimpanan lokal (mode fallback)
# ---------------------------------------------------------------------------
def _load_local_db() -> Dict[str, Any]:
    path = Path(LOCAL_AUTH_DB)
    if not path.exists():
        return {"users": {}, "resets": {}}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {"users": {}, "resets": {}}
    data.setdefault("users", {})
    data.setdefault("resets", {})
    return data


def _save_local_db(data: Dict[str, Any]) -> None:
    path = Path(LOCAL_AUTH_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Klien Identity Toolkit REST
# ---------------------------------------------------------------------------
class FirebaseAuthClient:
    """Pembungkus REST API Firebase Authentication (Identity Toolkit)."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 15):
        # `api_key=""` berarti sengaja tanpa kunci (mode lokal untuk pengujian),
        # sehingga tidak boleh digantikan dengan kunci bawaan.
        self.api_key = get_firebase_api_key() if api_key is None else api_key
        self.timeout = timeout
        self.base = f"https://identitytoolkit.googleapis.com/v1/accounts:"

    def _post(self, method: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        if not self.api_key:
            return False, {
                "message": "Firebase API key belum dikonfigurasi (mode lokal aktif)."
            }
        url = f"{self.base}{method}?key={self.api_key}"
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8") or "{}")
                return True, body
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode("utf-8") or "{}")
            except Exception:
                body = {}
            return False, body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return False, {"message": f"Gagal menghubungi Firebase Authentication: {exc}"}
        except json.JSONDecodeError:
            return False, {"message": "Respons Firebase tidak dapat dibaca."}

    # -- API publik ---------------------------------------------------------
    def sign_up(self, email: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        ok, body = self._post(
            "signUp", {"email": email, "password": password, "returnSecureToken": True}
        )
        return ok, body

    def sign_in(self, email: str, password: str) -> Tuple[bool, Dict[str, Any]]:
        ok, body = self._post(
            "signInWithPassword",
            {"email": email, "password": password, "returnSecureToken": True},
        )
        return ok, body

    def send_password_reset(self, email: str) -> Tuple[bool, Dict[str, Any]]:
        ok, body = self._post("sendOobCode", {"requestType": "PASSWORD_RESET", "email": email})
        return ok, body

    def verify_password_reset(self, oob_code: str) -> Tuple[bool, Dict[str, Any]]:
        ok, body = self._post("resetPassword", {"oobCode": oob_code})
        return ok, body

    def set_new_password(self, oob_code: str, new_password: str) -> Tuple[bool, Dict[str, Any]]:
        ok, body = self._post(
            "resetPassword", {"oobCode": oob_code, "newPassword": new_password}
        )
        return ok, body


# ---------------------------------------------------------------------------
# Layanan autentikasi tingkat aplikasi
# ---------------------------------------------------------------------------
class AuthService:
    """Fasad autentikasi: mencoba Firebase, lalu jatuh ke penyimpanan lokal."""

    def __init__(self, client: Optional[FirebaseAuthClient] = None):
        self.client = client or FirebaseAuthClient()
        self.last_mode: str = "local"

    # -- mode ---------------------------------------------------------------
    @property
    def using_firebase(self) -> bool:
        return bool(self.client.api_key)

    # -- pendaftaran --------------------------------------------------------
    def sign_up(self, email: str, password: str, confirm: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Daftarkan pengguna baru. Mengembalikan (berhasil, pesan, data pengguna)."""
        email = (email or "").strip().lower()
        error = validate_email(email)
        if error:
            return False, error, {}
        if password != confirm:
            return False, "Konfirmasi kata sandi tidak cocok.", {}
        strength = validate_password_strength(password)
        if strength:
            return False, strength, {}

        if self.using_firebase:
            ok, body = self.client.sign_up(email, password)
            if ok:
                self.last_mode = "firebase"
                display_name = body.get("displayName") or email.split("@")[0]
                data = _load_local_db()
                data["users"].setdefault(email, {})["display_name"] = display_name
                _save_local_db(data)
                return True, "Pendaftaran berhasil.", {
                    "uid": body.get("localId", ""),
                    "email": body.get("email", email),
                    "display_name": display_name,
                }
            message = _translate_firebase_error(body)
            # EMAIL_EXISTS pada mode lokal juga harus ditolak.
            if "already" in message.lower() or "sudah" in message.lower():
                return False, message, {}
            # Gagal attainment -> coba simpan secara lokal agar tetap bisa masuk.
            local_ok, local_msg, local_user = self._sign_up_local(email, password)
            if local_ok:
                self.last_mode = "local"
                return True, "Pendaftaran berhasil (mode lokal, Firebase tidak terjangkau).", local_user
            return False, message, {}

        return self._sign_up_local(email, password)

    def _sign_up_local(self, email: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
        data = _load_local_db()
        if email in data["users"]:
            return False, "Surel sudah terdaftar. Silakan masuk.", {}
        data["users"][email] = {
            "password_hash": hash_password(password),
            "created_at": datetime.now(WIB_OFFSET).isoformat(),
            "display_name": email.split("@")[0],
        }
        _save_local_db(data)
        return True, "Pendaftaran berhasil (mode lokal).", {
            "uid": hashlib.sha1(email.encode()).hexdigest()[:16],
            "email": email,
            "display_name": email.split("@")[0],
        }

    # -- masuk --------------------------------------------------------------
    def sign_in(self, email: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Masuk ke sistem. Mengembalikan (berhasil, pesan, data pengguna)."""
        email = (email or "").strip().lower()
        error = validate_email(email)
        if error:
            return False, error, {}

        if self.using_firebase:
            ok, body = self.client.sign_in(email, password)
            if ok:
                self.last_mode = "firebase"
                local_profile = _load_local_db().get("users", {}).get(email, {})
                display_name = local_profile.get("display_name") or body.get(
                    "displayName", email.split("@")[0]
                )
                return True, "Berhasil masuk.", {
                    "uid": body.get("localId", ""),
                    "email": body.get("email", email),
                    "display_name": display_name,
                    "id_token": body.get("idToken", ""),
                }
            message = _translate_firebase_error(body)
            # Fallback ke penyimpanan lokal bila Firebase menolak kredensial.
            local_ok, local_msg, local_user = self._sign_in_local(email, password)
            if local_ok:
                self.last_mode = "local"
                return True, "Berhasil masuk (mode lokal).", local_user
            return False, message, {}

        return self._sign_in_local(email, password)

    def _sign_in_local(self, email: str, password: str) -> Tuple[bool, str, Dict[str, Any]]:
        data = _load_local_db()
        record = data["users"].get(email)
        if not record:
            return False, "Surel atau kata sandi salah.", {}
        if not verify_password(password, record.get("password_hash", "")):
            return False, "Surel atau kata sandi salah.", {}
        return True, "Berhasil masuk (mode lokal).", {
            "uid": hashlib.sha1(email.encode()).hexdigest()[:16],
            "email": email,
            "display_name": record.get("display_name", email.split("@")[0]),
        }

    # -- lupa kata sandi ----------------------------------------------------
    def request_password_reset(self, email: str) -> Tuple[bool, str]:
        """Kirim tautan / token reset kata sandi."""
        email = (email or "").strip().lower()
        error = validate_email(email)
        if error:
            return False, error

        if self.using_firebase:
            ok, body = self.client.send_password_reset(email)
            if ok:
                return True, "Tautan reset kata sandi telah dikirim ke surel Anda."
            message = _translate_firebase_error(body)
            if "not found" in message.lower() or "tidak ditemukan" in message.lower():
                # Tetap buat token lokal agar alur tetap dapat didemokan.
                token = self._create_local_reset(email)
                return True, (
                    "Surel belum terdaftar pada Firebase. "
                    f"Token reset (mode lokal): {token}"
                )
            return False, message

        token = self._create_local_reset(email)
        data = _load_local_db()
        if email not in data["users"]:
            return True, (
                "Surel belum terdaftar, namun token reset lokal telah dibuat "
                f"untuk keperluan pengujian: {token}"
            )
        return True, f"Token reset (mode lokal): {token}"

    def _create_local_reset(self, email: str) -> str:
        data = _load_local_db()
        token = secrets.token_urlsafe(24)
        data["resets"][token] = {
            "email": email,
            "expires": (datetime.now(WIB_OFFSET) + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)).isoformat(),
        }
        _save_local_db(data)
        return token

    def reset_password(self, token: str, new_password: str, confirm: str) -> Tuple[bool, str]:
        """Terapkan kata sandi baru dari token reset."""
        if not token:
            return False, "Token reset wajib diisi."
        if new_password != confirm:
            return False, "Konfirmasi kata sandi tidak cocok."
        strength = validate_password_strength(new_password)
        if strength:
            return False, strength

        if self.using_firebase:
            ok, body = self.client.set_new_password(token, new_password)
            if ok:
                return True, "Kata sandi berhasil diperbarui."

        data = _load_local_db()
        record = data["resets"].get(token)
        if not record:
            return False, "Token reset tidak valid atau telah dipakai."
        try:
            expires = datetime.fromisoformat(record["expires"])
        except ValueError:
            expires = datetime.now(WIB_OFFSET) - timedelta(minutes=1)
        if expires < datetime.now(WIB_OFFSET):
            data["resets"].pop(token, None)
            _save_local_db(data)
            return False, "Token reset telah kedaluwarsa."

        email = record["email"]
        if email not in data["users"]:
            return False, "Surel tidak terdaftar pada penyimpanan lokal."

        data["users"][email]["password_hash"] = hash_password(new_password)
        data["resets"].pop(token, None)
        _save_local_db(data)
        return True, "Kata sandi berhasil diperbarui."

    def update_display_name(
        self, email: str, display_name: str
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Perbarui nama tampilan pengguna (disimpan lokal + sesi)."""
        email = (email or "").strip().lower()
        display_name = (display_name or "").strip()
        if not email:
            return False, "Surel tidak valid.", {}
        if len(display_name) < 2:
            return False, "Nama tampilan minimal 2 karakter.", {}
        if len(display_name) > 64:
            return False, "Nama tampilan maksimal 64 karakter.", {}

        data = _load_local_db()
        record = data["users"].setdefault(email, {})
        record["display_name"] = display_name
        record["updated_at"] = datetime.now(WIB_OFFSET).isoformat()
        if "created_at" not in record:
            record["created_at"] = record["updated_at"]
        _save_local_db(data)

        user = {
            "uid": hashlib.sha1(email.encode()).hexdigest()[:16],
            "email": email,
            "display_name": display_name,
        }
        if email in data["users"] and data["users"][email].get("password_hash"):
            user["uid"] = hashlib.sha1(email.encode()).hexdigest()[:16]
        return True, "Profil berhasil diperbarui.", user


def _translate_firebase_error(body: Dict[str, Any]) -> str:
    """Terjemahkan pesan galat Firebase ke bahasa Indonesia."""
    message = body.get("error", {}).get("message", "") if isinstance(body, dict) else ""
    if not message:
        message = body.get("message", "") if isinstance(body, dict) else ""
    mapping = {
        "EMAIL_EXISTS": "Surel sudah terdaftar. Silakan masuk.",
        "EMAIL_NOT_FOUND": "Surel tidak terdaftar.",
        "INVALID_PASSWORD": "Surel atau kata sandi salah.",
        "INVALID_LOGIN_CREDENTIALS": "Surel atau kata sandi salah.",
        "USER_DISABLED": "Akun ini telah dinonaktifkan.",
        "TOO_MANY_ATTEMPTS_TRY_LATER": "Terlalu banyak percobaan. Coba lagi nanti.",
        "WEAK_PASSWORD": "Kata sandi terlalu lemah.",
        "MISSING_PASSWORD": "Kata sandi wajib diisi.",
        "OPERATION_NOT_ALLOWED": "Metode autentikasi email/sandi belum diaktifkan di Firebase Console.",
    }
    for key, value in mapping.items():
        if key in message:
            return value
    return message or "Terjadi kesalahan pada proses autentikasi."
