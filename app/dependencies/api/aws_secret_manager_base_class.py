from abc import ABC, abstractmethod

class AwsSecretManagerBaseClass(ABC):

    """
    Retrieves a secret to be used for RDS.
    """
    @abstractmethod
    async def get_rds_secret() -> str:
        pass
