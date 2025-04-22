from fastapi import Header
from typing import Dict

from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class FakeAwsCognitoClient(AwsCognitoBaseClass):

    def verify_cognito_token(self, auth_header: str = Header(...)) -> Dict:
        pass

    def decode_cognito_token(self, token: str) -> Dict:
        pass

    def get_jwk_client(self):
        pass

    async def delete_user(self, user_id: str):
        pass
