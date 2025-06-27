from abc import ABC, abstractmethod

from .resend_base_class import ResendBaseClass

class AwsSecretManagerBaseClass(ABC):

    @abstractmethod
    async def get_secret(
        self,
        secret_id: str,
        resend_client: ResendBaseClass,
    ) -> dict:
        """
        Retrieves a secret.
        """
        pass
