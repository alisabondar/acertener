from datetime import date
from typing import Any

from sqlalchemy import Dialect, Text
from sqlalchemy.types import TypeDecorator

from app.crypto import FieldCipher

_cipher: FieldCipher | None = None


class CipherNotConfiguredError(RuntimeError):
    """An encrypted column was used before the app registered its cipher."""


def set_field_cipher(cipher: FieldCipher | None) -> None:
    """Register the process-wide cipher used by encrypted columns (done once at startup)."""
    global _cipher
    _cipher = cipher


def get_field_cipher() -> FieldCipher:
    if _cipher is None:
        raise CipherNotConfiguredError("no field cipher registered; refusing to store plaintext")
    return _cipher


class EncryptedText(TypeDecorator[str]):
    """Text that is encrypted on write and decrypted on read. NULL stays NULL."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        return None if value is None else get_field_cipher().encrypt(value)

    def process_result_value(self, value: Any | None, dialect: Dialect) -> str | None:
        return None if value is None else get_field_cipher().decrypt(value)


class EncryptedDate(TypeDecorator[date]):
    """A date stored as encrypted ISO text (e.g. date of birth)."""

    impl = EncryptedText
    cache_ok = True

    def process_bind_param(self, value: date | None, dialect: Dialect) -> str | None:
        return None if value is None else value.isoformat()

    def process_result_value(self, value: Any | None, dialect: Dialect) -> date | None:
        return None if value is None else date.fromisoformat(value)
