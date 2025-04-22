import boto3
import os

from ..api.aws_cognito_base_class import AwsCognitoBaseClass
from ..boto3_client_factory import Boto3ClientFactory

class AwsCognitoClient(AwsCognitoBaseClass):

    def __init__(self):
        self.user_pool_id = os.environ.get("AWS_COGNITO_USER_POOL_ID")
        self.client = Boto3ClientFactory.get_client("cognito-idp")

    async def delete_user(self, user_id: str):
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=user_id
            )
        except Exception as e:
            raise RuntimeError(f"Error deleting user: {e}") from e
