from fastapi import Header
from typing import Dict

from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class FakeAwsCognitoClient(AwsCognitoBaseClass):

    FAKE_ENCODED_COGNITO_TOKEN = {
        "sub": "test-user-id",
        "email": "test@example.com",
        "claims": {"cognito:groups": ["therapist"]}
    }

    FAKE_DECODED_COGNITO_TOKEN = {
        "sub": "test-user-id",
        "email": "test@example.com",
    }

    return_valid_tokens = True
    invoked_delete_user = False

    def verify_cognito_token(self, token: str) -> Dict:
        return self.FAKE_ENCODED_COGNITO_TOKEN if self.return_valid_tokens else {}

    def decode_cognito_token(self, token: str) -> Dict:
        return self.FAKE_DECODED_COGNITO_TOKEN if self.return_valid_tokens else {}

    def get_jwk_client(self):
        pass

    async def delete_user(self, user_id: str):
        self.invoked_delete_user = True
