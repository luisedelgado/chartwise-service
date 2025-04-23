import base64

from nacl.secret import Aead

from ...dependencies.api.aws_kms_base_class import AwsKmsBaseClass

class ChartWiseEncryptor:
    """
    A utility class for encrypting and decrypting data using the AEAD (Authenticated Encryption with Associated Data) scheme. 
    This class leverages the `nacl.secret.Aead` library to provide secure encryption and decryption.
    """
    def __init__(
        self,
        aws_kms_client: AwsKmsBaseClass
    ):
        encryption_key = aws_kms_client.decrypt_encryption_key_ciphertext()
        if len(encryption_key) != Aead.KEY_SIZE:
            raise ValueError("Decrypted key is not 32 bytes")

        self.aead = Aead(encryption_key)

    """
    Encrypts the incoming plaintext string.

    Params:
    -------
    plaintext: The plaintext to be encrypted.
    """
    def encrypt(
        self,
        plaintext: str
    ) -> bytes:
        if plaintext is None:
            return plaintext

        return self.aead.encrypt(plaintext.encode("utf-8"), None)

    """
    Decrypts the incoming bytes.

    Params:
    -------
    ciphertext: The bytes to be decrypted.
    """
    def decrypt(
        self,
        ciphertext: bytes
    ) -> str:
        if ciphertext is None:
            return None

        try:
            plaintext_bytes = self.aead.decrypt(ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError("Decryption failed") from e
