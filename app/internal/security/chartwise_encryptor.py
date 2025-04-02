import base64

from nacl.secret import Aead

from ...dependencies.api.aws_kms_base_class import AwsKmsBaseClass

class ChartWiseEncryptor:
    """
    A utility class for encrypting and decrypting data using the AEAD (Authenticated Encryption with Associated Data) scheme. 
    This class leverages the `nacl.secret.Aead` library to provide secure encryption and decryption.
    """
    def __init__(self, aws_kms_client: AwsKmsBaseClass):
        encryption_key = aws_kms_client.decrypt_encryption_key_ciphertext()
        if len(encryption_key) != Aead.KEY_SIZE:
            raise ValueError("Decrypted key is not 32 bytes")

        self.aead = Aead(encryption_key)

    def encrypt(self, plaintext: str) -> str:
        if plaintext is None:
            return plaintext

        ciphertext = self.aead.encrypt(plaintext.encode("utf-8"), None)
        # Encode ciphertext to Base64 for JSON serialization
        encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).decode('utf-8')
        return encoded_ciphertext

    """
    Decrypts a base64 encoded ciphertext. Used for BYTEA values coming from Postgres DBs

    Params:
    -------
    b64_encoded_ciphertext_bytes: The base64 encoded ciphertext to decrypt.
    """
    def decrypt_b64_encoded_ciphertext(self, b64_encoded_ciphertext_bytes: str) -> str:
        if b64_encoded_ciphertext_bytes is None:
            return b64_encoded_ciphertext_bytes

        try:
            b64_str = b64_encoded_ciphertext_bytes.decode("utf-8")
            return self.decrypt_base64_str(b64_str)
        except Exception as e:
            raise ValueError("Decoding operation failed")

    """
    Decrypts a base64 string. Used for base64 string.

    Params:
    -------
    b64_str: The base64 string to decrypt.
    """
    def decrypt_base64_str(self, b64_str: str) -> str:
        if b64_str is None:
            return b64_str

        try:
            ciphertext = base64.urlsafe_b64decode(b64_str)
            plaintext_bytes = self.aead.decrypt(ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decoding operation failed")
