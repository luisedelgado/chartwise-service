import os
import base64

from fastapi import HTTPException, status
from pydantic import BaseModel
from nacl.secret import Aead
from nacl.utils import random

AUTH_TOKEN_EXPIRED_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Token missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

STORE_TOKENS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="One or more store token headers are missing or expired",
    headers={"WWW-Authenticate": "Bearer"},
)

class Token(BaseModel):
    authorization: str
    token_type: str
    expiration_timestamp: str

class ChartWiseEncryptor:
    """
    A utility class for encrypting and decrypting data using the AEAD (Authenticated Encryption with Associated Data) scheme. 
    This class leverages the `nacl.secret.Aead` library to provide secure encryption and decryption.

    Attributes:
    -----------
    key : bytes
        The encryption key derived from the environment variable. Must be 32 bytes (64 hex characters).
    aead : Aead
        An instance of the AEAD encryption object initialized with the encryption key.
    """
    def __init__(self):
        encryption_key = "CHARTWISE_PHI_ENCRYPTION_KEY"
        key_hex: str = os.environ.get(encryption_key)
        if not key_hex:
            raise ValueError(f"Missing encryption key in env var: {encryption_key}")
        key_bytes = bytes.fromhex(key_hex)
        if len(key_bytes) != Aead.KEY_SIZE:
            raise ValueError("Encryption key must be 32 bytes (64 hex characters)")
        self.key = key_bytes
        self.aead = Aead(self.key)

    def encrypt(self, plaintext: str) -> str:
        ciphertext = self.aead.encrypt(plaintext.encode("utf-8"), None)
        # Encode ciphertext to Base64 for JSON serialization
        encoded_ciphertext = base64.urlsafe_b64encode(ciphertext).decode('utf-8')
        return encoded_ciphertext

    def decrypt(self, base64_bytes: str) -> str:
        try:
            b64_str = base64_bytes.decode("utf-8")
            ciphertext = base64.urlsafe_b64decode(b64_str)
            plaintext_bytes = self.aead.decrypt(ciphertext, None)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Base64 decoding failed: {str(e)}")
