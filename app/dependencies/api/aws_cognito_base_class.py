from abc import ABC, abstractmethod
from fastapi import Header
from typing import Dict

class AwsCognitoBaseClass(ABC):

    @abstractmethod
    def verify_cognito_token(auth_header: str = Header(...)) -> Dict:
        """
        Verifies the Cognito token.
        Arguments:
        auth_header – the authorization header containing the Cognito token.
        """
        pass

    @abstractmethod
    def decode_cognito_token(token: str) -> Dict:
        """
        Decodes the Cognito token.
        Arguments:
        token – the Cognito token to decode.
        """
        pass

    @abstractmethod
    def get_jwk_client():
        """
        Returns the JWK client for Cognito.
        """
        pass

    @abstractmethod
    async def delete_user(user_id: str):
        """
        Deletes a user from the Cognito auth system.
        Arguments:
        user_id – the current user ID.
        """
        pass
