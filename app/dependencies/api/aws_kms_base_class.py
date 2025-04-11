from abc import ABC, abstractmethod

class AwsKmsBaseClass(ABC):

    @abstractmethod
    def decrypt_encryption_key_ciphertext(ciphertext: str) -> str:
        """
        Returns the derypted encryption key, if any.
        """
        pass
