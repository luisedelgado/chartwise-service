from abc import ABC, abstractmethod

class AwsCognitoBaseClass(ABC):

    @abstractmethod
    async def delete_user(user_id: str):
        """
        Deletes a user from the Cognito auth system.
        Arguments:
        user_id – the current user ID.
        """
        pass
