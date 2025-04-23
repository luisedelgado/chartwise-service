from abc import ABC, abstractmethod

class AwsSecretManagerBaseClass(ABC):

    @abstractmethod
    async def get_secret(
        secret_id: str
    ) -> str:
        """
        Retrieves a secret.
        """
        pass
