from abc import ABC, abstractmethod

from .resend_base_class import ResendBaseClass

class AwsSecretManagerBaseClass(ABC):

    @abstractmethod
    async def get_secret(
        secret_id: str,
        resend_client: ResendBaseClass,
    ) -> str:
        """
        Retrieves a secret.
        """
        pass
