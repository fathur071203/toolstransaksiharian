"""
SAKSI — Autentikasi pengguna
============================
Backend login sederhana berbasis file Excel lokal (`data/users.xlsx`).

Prinsip keamanan:
  - Password TIDAK PERNAH disimpan plaintext. Selalu di-hash dengan
    PBKDF2-SHA256 (salt acak per pengguna), format:
        pbkdf2_sha256$<iterasi>$<salt_hex>$<hash_hex>
  - Verifikasi memakai perbandingan waktu-konstan (hmac.compare_digest).

Tabel pengguna (kolom users.xlsx):
    username, email, password_hash, full_name, unit, role, status, created_at

Fungsi publik:
    login_user(username, password)   -> (success, message, user_dict | None)
    register_user(...)               -> (success, message)
    get_user_by_username(username)   -> dict | None
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime
from typing import Optional

import pandas as pd

# ----------------------------------------------------------------------------
# Lokasi & skema
# ----------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_PATH = os.path.join(_DIR, "data", "users.xlsx")

KOLOM = ["username", "email", "password_hash", "full_name",
         "unit", "role", "status", "created_at"]

_ITERASI = 200_000

# Akun bawaan saat file users.xlsx belum ada (HARAP GANTI PASSWORD setelah login).
_DEFAULT_ADMIN = {
    "username": "admin",
    "email": "admin@bi.go.id",
    "password": "admin123",
    "full_name": "Administrator SAKSI",
    "unit": "KPwBI Provinsi DKI Jakarta",
    "role": "admin",
}


# ----------------------------------------------------------------------------
# Hashing password
# ----------------------------------------------------------------------------
def hash_password(password: str, iterations: int = _ITERASI) -> str:
    """Kembalikan string hash 'pbkdf2_sha256$iter$salt$hash'."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verifikasi password terhadap hash tersimpan (waktu-konstan)."""
    try:
        algo, iters, salt, hsh = str(stored).split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), hsh)
    except (ValueError, AttributeError):
        return False


# ----------------------------------------------------------------------------
# Penyimpanan (Excel lokal)
# ----------------------------------------------------------------------------
def _ensure_users_file() -> pd.DataFrame:
    """Pastikan data/users.xlsx ada; buat dengan admin bawaan bila belum."""
    os.makedirs(os.path.dirname(USERS_PATH), exist_ok=True)
    if not os.path.exists(USERS_PATH):
        admin = {
            "username": _DEFAULT_ADMIN["username"],
            "email": _DEFAULT_ADMIN["email"],
            "password_hash": hash_password(_DEFAULT_ADMIN["password"]),
            "full_name": _DEFAULT_ADMIN["full_name"],
            "unit": _DEFAULT_ADMIN["unit"],
            "role": _DEFAULT_ADMIN["role"],
            "status": "active",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        df = pd.DataFrame([admin], columns=KOLOM)
        df.to_excel(USERS_PATH, index=False)
        return df
    return _read_users()


def _read_users() -> pd.DataFrame:
    df = pd.read_excel(USERS_PATH, dtype=str).fillna("")
    for k in KOLOM:
        if k not in df.columns:
            df[k] = ""
    return df[KOLOM]


def _write_users(df: pd.DataFrame) -> None:
    df.to_excel(USERS_PATH, index=False)


# ----------------------------------------------------------------------------
# API publik
# ----------------------------------------------------------------------------
def get_user_by_username(username: str) -> Optional[dict]:
    df = _ensure_users_file()
    u = str(username).strip().lower()
    hit = df[df["username"].str.strip().str.lower() == u]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def login_user(username: str, password: str):
    """Validasi kredensial. -> (success: bool, message: str, user: dict | None)."""
    user = get_user_by_username(username)
    if user is None:
        return False, "Username tidak ditemukan", None
    if str(user.get("status", "active")).lower() not in ("active", ""):
        return False, "Akun nonaktif — hubungi administrator", None
    if not verify_password(password, user.get("password_hash", "")):
        return False, "Password salah", None
    aman = {k: v for k, v in user.items() if k != "password_hash"}
    return True, f"Selamat datang, {user.get('full_name') or user.get('username')}", aman


def register_user(username: str, password: str, email: str = "",
                  full_name: str = "", unit: str = "", role: str = "viewer"):
    """Tambah pengguna baru. -> (success: bool, message: str)."""
    df = _ensure_users_file()
    u = str(username).strip()
    if not u or not password:
        return False, "Username dan password wajib diisi"
    if (df["username"].str.strip().str.lower() == u.lower()).any():
        return False, "Username sudah terdaftar"
    baru = {
        "username": u, "email": email, "password_hash": hash_password(password),
        "full_name": full_name, "unit": unit, "role": role, "status": "active",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    df = pd.concat([df, pd.DataFrame([baru], columns=KOLOM)], ignore_index=True)
    _write_users(df)
    return True, "Pengguna berhasil didaftarkan"
