import base64
import logging
import re
import stat
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.crypto import KeyFileError, Keys, load_or_create_keys


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_missing_keys_are_generated_with_private_permissions(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"

    keys = load_or_create_keys(keys_dir)

    assert len(keys.field_keys) == 1
    assert _mode(keys_dir) == 0o700
    assert _mode(keys_dir / "field.keys") == 0o600
    assert _mode(keys_dir / "fingerprint.key") == 0o600


def test_existing_keys_are_reused(tmp_path: Path) -> None:
    first = load_or_create_keys(tmp_path)
    second = load_or_create_keys(tmp_path)

    assert first == second


def test_field_keys_file_lists_newest_first_and_ignores_blank_lines(tmp_path: Path) -> None:
    new_key, old_key = Fernet.generate_key(), Fernet.generate_key()
    load_or_create_keys(tmp_path)
    (tmp_path / "field.keys").write_bytes(new_key + b"\n\n" + old_key + b"\n")

    keys = load_or_create_keys(tmp_path)

    assert keys.field_keys == [new_key, old_key]


def test_key_generation_is_logged_without_key_material(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    keys = load_or_create_keys(tmp_path)

    assert any("generated" in r.getMessage() for r in caplog.records)
    for secret in [*keys.field_keys, keys.fingerprint_key]:
        assert secret.decode() not in caplog.text


@pytest.mark.parametrize("filename", ["field.keys", "fingerprint.key"])
def test_corrupt_key_file_raises_without_revealing_its_contents(
    tmp_path: Path, filename: str
) -> None:
    load_or_create_keys(tmp_path)
    garbage = "not-a-real-key-CANARY"
    (tmp_path / filename).write_text(garbage)

    with pytest.raises(KeyFileError, match=re.escape(filename)) as caught:
        load_or_create_keys(tmp_path)

    assert garbage not in str(caught.value)
    assert caught.value.__cause__ is None


def test_empty_field_keys_file_is_an_error(tmp_path: Path) -> None:
    load_or_create_keys(tmp_path)
    (tmp_path / "field.keys").write_text("\n")

    with pytest.raises(KeyFileError, match=r"field\.keys"):
        load_or_create_keys(tmp_path)


def test_fingerprint_key_of_the_wrong_length_is_an_error(tmp_path: Path) -> None:
    load_or_create_keys(tmp_path)
    (tmp_path / "fingerprint.key").write_bytes(base64.urlsafe_b64encode(b"too short"))

    with pytest.raises(KeyFileError, match=r"fingerprint\.key"):
        load_or_create_keys(tmp_path)


def test_concurrent_first_runs_agree_on_one_set_of_keys(tmp_path: Path) -> None:
    keys_dir = tmp_path / "keys"
    barrier = threading.Barrier(16)

    def start() -> Keys:
        barrier.wait()
        return load_or_create_keys(keys_dir)

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: start(), range(16)))

    assert all(keys == results[0] for keys in results)
