import hashlib
import hmac
import unicodedata
from collections.abc import Sequence
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.crypto.keys import decode_fingerprint_key

V1_TAG = "v1:"


class DecryptionError(Exception):
    """A stored value could not be decrypted. Never carries the value itself."""

    def __init__(self) -> None:
        super().__init__("value could not be decrypted")


class FieldCipher(Protocol):
    """The only interface models and services use. A v2 scheme is a new implementation."""

    def encrypt(self, plaintext: str) -> str: ...

    def decrypt(self, stored: str) -> str: ...

    def fingerprint(self, purpose: str, value: str) -> bytes: ...


def normalize(value: str) -> str:
    """Case-, width-, and whitespace-insensitive form used for exact-match search."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class FernetFieldCipher:
    """v1: MultiFernet (newest key encrypts, all keys decrypt) plus HMAC-SHA256 fingerprints."""

    def __init__(self, field_keys: Sequence[bytes], fingerprint_key: bytes) -> None:
        if not field_keys:
            raise ValueError("FernetFieldCipher needs at least one field key")
        self._fernet = MultiFernet([Fernet(key) for key in field_keys])
        self._fingerprint_key = decode_fingerprint_key(fingerprint_key)

    def encrypt(self, plaintext: str) -> str:
        return V1_TAG + self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, stored: str) -> str:
        if not stored.startswith(V1_TAG):
            raise DecryptionError
        try:
            return self._fernet.decrypt(stored.removeprefix(V1_TAG).encode()).decode()
        except InvalidToken:
            raise DecryptionError from None

    def fingerprint(self, purpose: str, value: str) -> bytes:
        # The purpose is part of the input, so equal values in different columns don't match.
        message = purpose.encode() + b"\x00" + normalize(value).encode()
        return hmac.new(self._fingerprint_key, message, hashlib.sha256).digest()
