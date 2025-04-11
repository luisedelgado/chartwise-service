from abc import ABC, abstractmethod

class AwsSecretManagerBaseClass(ABC):

    @abstractmethod
    async def get_rds_secret() -> str:
        """
        Retrieves a secret to be used for RDS.
        """
        pass
