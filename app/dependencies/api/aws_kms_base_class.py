from abc import ABC, abstractmethod

class AwsKmsBaseClass(ABC):

    @abstractmethod
    def decrypt_encryption_key_ciphertext() -> str:
        """
        Returns the derypted encryption key, if any.
        """
        pass
