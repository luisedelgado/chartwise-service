from fastapi import Header
from typing import Dict

from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class FakeAwsCognitoClient(AwsCognitoBaseClass):

    def verify_cognito_token(self, auth_header: str = Header(...)) -> Dict:
        return {
            "sub": "test-user-id",
            "email": "test@example.com",
            "claims": {"cognito:groups": ["therapist"]}
        }

    def decode_cognito_token(self, token: str) -> Dict:
        return {
            "sub": "test-user-id",
            "email": "test@example.com",
        }

    def get_jwk_client(self):
        pass

    async def delete_user(self, user_id: str):
        pass
