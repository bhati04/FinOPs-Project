"""AWS connection encryption tests."""

from cryptography.fernet import Fernet

from cloudwise.aws_accounts.encryption import ExternalIdCipher


def test_external_id_is_encrypted_and_round_trips() -> None:
    cipher = ExternalIdCipher(Fernet.generate_key().decode("ascii"))
    external_id = "d941319c-8c1d-4f96-88ef-a87a9360e422"

    encrypted = cipher.encrypt(external_id)

    assert external_id.encode() not in encrypted
    assert cipher.decrypt(encrypted) == external_id
