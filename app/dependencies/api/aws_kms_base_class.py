from abc import ABC, abstractmethod

from .resend_base_class import ResendBaseClass

class AwsKmsBaseClass(ABC):

    @abstractmethod
    def decrypt_encryption_key_ciphertext(
        self,
        resend_client: ResendBaseClass
    ) -> str:
        """
        Returns the derypted encryption key, if any.
        """
        pass
