"""學習中心本機帳號的密碼雜湊。

用標準函式庫的 PBKDF2-HMAC-SHA256，不另外加 bcrypt/argon2 相依套件。
存放格式：`pbkdf2_sha256$<iterations>$<salt hex>$<hash hex>`，之後要調高
迭代次數時舊雜湊仍然驗得過。
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets

_ITERATIONS = 240_000
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email or ""))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)
