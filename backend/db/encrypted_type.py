from __future__ import annotations
import os
import base64
import hmac
import hashlib
import logging
from typing import Optional, Any
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from sqlalchemy.types import TypeDecorator, String, Text

logger = logging.getLogger(__name__)

def _get_multifernet() -> MultiFernet:
    keys = []
    primary = os.getenv("FIELD_ENCRYPTION_KEY")
    if primary:
        keys.append(primary.strip())
    secondary = os.getenv("FIELD_ENCRYPTION_KEY_FALLBACK")
    if secondary:
        keys.append(secondary.strip())
    
    if not keys:
        dev_key = base64.urlsafe_b64encode(hashlib.sha256(b"bank-loan-dev-field-key").digest()).decode()
        keys.append(dev_key)

    fernets = []
    for k in keys:
        try:
            fernets.append(Fernet(k.encode() if isinstance(k, str) else k))
        except Exception as exc:
            logger.warning("Invalid fernet key in configuration: %s", exc)
    
    if not fernets:
        raise RuntimeError("No valid encryption keys configured.")
    return MultiFernet(fernets)

def _deterministic_encrypt(raw_bytes: bytes, fernet: Fernet) -> str:
    """
    Deterministic Fernet-compatible encryption for exact-equality searchable fields (e.g., User.email).

    SECURITY TRADEOFF & DESIGN:
    Standard Fernet encryption uses randomized IVs (os.urandom) and current timestamps, which
    guarantees CPA security (different ciphertexts for identical plaintexts), but prevents database
    equality searches (WHERE email = :query) and unique database indexes.

    This function implements a Synthetic IV (SIV-like) approach:
    1. Derives a deterministic IV using HMAC-SHA256(encryption_key, plaintext)[:16].
    2. Uses AES-128-CBC with the derived IV and PKCS7 padding.
    3. Formats the output with Fernet header (\x80 + zero timestamp + IV + ciphertext + HMAC-SHA256).
    This allows exact SQL lookups while encrypting the data at rest in MySQL.
    For all other fields (names, incomes, balances), standard randomized Fernet is used.
    """
    signing_key = fernet._signing_key
    encryption_key = fernet._encryption_key

    iv = hmac.new(encryption_key, raw_bytes, hashlib.sha256).digest()[:16]
    padder = padding.PKCS7(128).padder()
    padded = padder.update(raw_bytes) + padder.finalize()
    encryptor = Cipher(algorithms.AES(encryption_key), modes.CBC(iv)).encryptor()
    ct = encryptor.update(padded) + encryptor.finalize()

    ts = (0).to_bytes(8, byteorder="big")
    basic_parts = b"\x80" + ts + iv + ct
    h = hmac.new(signing_key, basic_parts, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(basic_parts + h).decode()

class EncryptedString(TypeDecorator):
    """Encrypted String type supporting transparent MultiFernet encryption/decryption."""
    impl = String(255)
    cache_ok = True

    def __init__(self, length=255, deterministic=False, **kwargs):
        super().__init__(length=length, **kwargs)
        self.deterministic = deterministic

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        if value is None:
            return None
        s_val = str(value).strip()
        if not s_val:
            return s_val
        mf = _get_multifernet()
        raw = s_val.encode("utf-8")
        if self.deterministic:
            return _deterministic_encrypt(raw, mf._fernets[0])
        return mf.encrypt(raw).decode("utf-8")

    def process_result_value(self, value: Optional[str], dialect) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str) or not value.startswith("gAAAAA"):
            return str(value)
        mf = _get_multifernet()
        try:
            decrypted = mf.decrypt(value.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            return value
        except Exception:
            return value

class EncryptedFloat(TypeDecorator):
    """Encrypted Float type storing numbers as encrypted ciphertext."""
    impl = String(255)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Optional[str]:
        if value is None:
            return None
        try:
            f_val = float(value)
        except (ValueError, TypeError):
            return None
        mf = _get_multifernet()
        return mf.encrypt(str(f_val).encode("utf-8")).decode("utf-8")

    def process_result_value(self, value: Optional[str], dialect) -> Optional[float]:
        if value is None:
            return None
        if not isinstance(value, str) or not value.startswith("gAAAAA"):
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        mf = _get_multifernet()
        try:
            decrypted = mf.decrypt(value.encode("utf-8")).decode("utf-8")
            return float(decrypted)
        except (InvalidToken, ValueError, TypeError):
            return None
