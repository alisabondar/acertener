import base64
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger("app.crypto")

FIELD_KEYS_FILE = "field.keys"
FINGERPRINT_KEY_FILE = "fingerprint.key"


class KeyFileError(Exception):
    """A key file is unreadable. Names the file, never its contents."""


@dataclass(frozen=True)
class Keys:
    field_keys: list[bytes]  # newest first: the first key encrypts, all keys decrypt
    fingerprint_key: bytes


def decode_fingerprint_key(key: bytes) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(key)
    except ValueError:  # includes binascii.Error
        raise KeyFileError(FINGERPRINT_KEY_FILE) from None
    if len(raw) != 32:
        raise KeyFileError(FINGERPRINT_KEY_FILE)
    return raw


def _write_new_key(path: Path) -> None:
    """Publish a complete key file atomically; if another process wins the race, keep theirs."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")  # created 0600
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(Fernet.generate_key() + b"\n")
        os.link(tmp, path)
    except FileExistsError:
        return
    finally:
        os.unlink(tmp)
    logger.info("generated encryption key file", extra={"ctx": {"file": path.name}})


def load_or_create_keys(keys_dir: Path) -> Keys:
    """Load keys from `keys_dir`, generating any that are missing."""
    try:
        keys_dir.mkdir(parents=True)
        keys_dir.chmod(0o700)
    except FileExistsError:
        pass
    for name in (FIELD_KEYS_FILE, FINGERPRINT_KEY_FILE):
        if not (keys_dir / name).exists():
            _write_new_key(keys_dir / name)

    field_keys = [line for line in (keys_dir / FIELD_KEYS_FILE).read_bytes().split() if line]
    if not field_keys:
        raise KeyFileError(FIELD_KEYS_FILE)
    for key in field_keys:
        try:
            Fernet(key)
        except ValueError:
            raise KeyFileError(FIELD_KEYS_FILE) from None

    fingerprint_key = (keys_dir / FINGERPRINT_KEY_FILE).read_bytes().strip()
    decode_fingerprint_key(fingerprint_key)
    return Keys(field_keys=field_keys, fingerprint_key=fingerprint_key)
