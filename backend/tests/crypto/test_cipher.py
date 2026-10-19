import pytest
from cryptography.fernet import Fernet

from app.crypto import DecryptionError, FernetFieldCipher

CANARY = "CanarySmith"
FULLWIDTH_OBRIEN = "\uff2f'\uff22\uff52\uff49\uff45\uff4e"


def make_cipher(*field_keys: bytes, fingerprint_key: bytes | None = None) -> FernetFieldCipher:
    return FernetFieldCipher(
        field_keys=list(field_keys) or [Fernet.generate_key()],
        fingerprint_key=fingerprint_key or Fernet.generate_key(),
    )


@pytest.mark.parametrize("plaintext", ["Ada Lovelace", "", "José Ñúñez 😀"])
def test_round_trip(plaintext: str) -> None:
    cipher = make_cipher()

    assert cipher.decrypt(cipher.encrypt(plaintext)) == plaintext


def test_stored_values_are_v1_tagged_and_randomized() -> None:
    cipher = make_cipher()

    first, second = cipher.encrypt(CANARY), cipher.encrypt(CANARY)

    assert first.startswith("v1:")
    assert first != second
    assert CANARY not in first


def test_tampered_ciphertext_fails() -> None:
    cipher = make_cipher()
    token = cipher.encrypt(CANARY)
    middle = len(token) // 2
    tampered = token[:middle] + ("A" if token[middle] != "A" else "B") + token[middle + 1 :]

    with pytest.raises(DecryptionError):
        cipher.decrypt(tampered)


def test_wrong_key_fails() -> None:
    token = make_cipher().encrypt(CANARY)

    with pytest.raises(DecryptionError):
        make_cipher().decrypt(token)


@pytest.mark.parametrize("value", ["no-tag-at-all", "v2:something", "v1", ""])
def test_missing_or_unknown_tag_is_rejected(value: str) -> None:
    with pytest.raises(DecryptionError):
        make_cipher().decrypt(value)


def test_old_key_still_decrypts_after_rotation_and_new_values_use_the_new_key() -> None:
    old_key, new_key = Fernet.generate_key(), Fernet.generate_key()
    old_token = make_cipher(old_key).encrypt(CANARY)

    rotated = make_cipher(new_key, old_key)
    new_token = rotated.encrypt(CANARY)

    assert rotated.decrypt(old_token) == CANARY
    assert make_cipher(new_key).decrypt(new_token) == CANARY
    with pytest.raises(DecryptionError):
        make_cipher(old_key).decrypt(new_token)


@pytest.mark.privacy
def test_decryption_error_never_reveals_ciphertext_or_plaintext() -> None:
    token = make_cipher().encrypt(CANARY)

    with pytest.raises(DecryptionError) as caught:
        make_cipher().decrypt(token)

    for text in (str(caught.value), repr(caught.value)):
        assert CANARY not in text
        assert token not in text
    assert caught.value.__cause__ is None
    assert caught.value.__suppress_context__


def test_fingerprint_is_deterministic_and_normalized() -> None:
    cipher = make_cipher()

    reference = cipher.fingerprint("last_name", "O'Brien")

    assert len(reference) == 32
    for variant in ["O'Brien", "o'brien", "  O'BRIEN ", "O'Brien\t", FULLWIDTH_OBRIEN]:
        assert cipher.fingerprint("last_name", variant) == reference


def test_fingerprint_collapses_inner_whitespace() -> None:
    cipher = make_cipher()

    assert cipher.fingerprint("last_name", "Van  der\tBerg") == cipher.fingerprint(
        "last_name", "van der berg"
    )


def test_fingerprint_differs_between_purposes_and_keys() -> None:
    cipher = make_cipher()

    assert cipher.fingerprint("last_name", "1990-01-31") != cipher.fingerprint("dob", "1990-01-31")
    assert cipher.fingerprint("last_name", CANARY) != make_cipher().fingerprint("last_name", CANARY)


def test_fingerprint_does_not_depend_on_the_field_keys() -> None:
    fingerprint_key = Fernet.generate_key()

    first = make_cipher(fingerprint_key=fingerprint_key)
    second = make_cipher(fingerprint_key=fingerprint_key)

    assert first.fingerprint("dob", "1990-01-31") == second.fingerprint("dob", "1990-01-31")


def test_cipher_requires_at_least_one_field_key() -> None:
    with pytest.raises(ValueError, match="at least one field key"):
        FernetFieldCipher(field_keys=[], fingerprint_key=Fernet.generate_key())
