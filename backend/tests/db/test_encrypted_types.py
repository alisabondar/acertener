import pytest
from sqlalchemy.engine.default import DefaultDialect

from app.db.types import CipherNotConfiguredError, EncryptedText, set_field_cipher


def test_encrypted_columns_refuse_to_work_without_a_cipher() -> None:
    set_field_cipher(None)

    with pytest.raises(CipherNotConfiguredError):
        EncryptedText().process_bind_param("CanarySmith", DefaultDialect())
