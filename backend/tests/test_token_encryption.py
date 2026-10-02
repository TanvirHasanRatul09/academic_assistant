import pytest
from cryptography.fernet import Fernet

from app.services.token_encryption import TokenEncryption


def test_token_round_trip_and_ciphertext_does_not_contain_token() -> None:
    encryption = TokenEncryption(Fernet.generate_key().decode("ascii"))
    encrypted = encryption.encrypt("private-oauth-token")

    assert b"private-oauth-token" not in encrypted
    assert encryption.decrypt(encrypted) == "private-oauth-token"


def test_invalid_key_is_rejected() -> None:
    with pytest.raises(ValueError, match="valid Fernet key"):
        TokenEncryption("not-a-fernet-key")
