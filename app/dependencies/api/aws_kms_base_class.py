from abc import ABC, abstractmethod

class AwsKmsBaseClass(ABC):

    """
    Returns the derypted encryption key, if any.
    """
    @abstractmethod
    def decrypt_encryption_key_ciphertext(ciphertext: str) -> str:
        pass
