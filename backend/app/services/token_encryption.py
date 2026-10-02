from cryptography.fernet import Fernet, InvalidToken


class TokenEncryption:
    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt(self, token: str) -> bytes:
        return self._fernet.encrypt(token.encode("utf-8"))

    def decrypt(self, encrypted_token: bytes) -> str:
        try:
            return self._fernet.decrypt(encrypted_token).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("encrypted token could not be decrypted") from exc
