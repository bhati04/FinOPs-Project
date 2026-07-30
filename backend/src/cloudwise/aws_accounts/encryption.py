"""External ID encryption boundary."""

from cryptography.fernet import Fernet, InvalidToken


class ExternalIdCipher:
    """Encrypt and decrypt connection External IDs."""

    def __init__(self, key: str) -> None:
        self._fernet = Fernet(key.encode("ascii"))

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("External ID could not be decrypted") from exc
