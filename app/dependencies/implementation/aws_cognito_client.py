import boto3
import os

from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class AwsCognitoClient(AwsCognitoBaseClass):

    def __init__(self):
        self.user_pool_id = os.environ.get("AWS_COGNITO_USER_POOL_ID")
        self.client = boto3.client('cognito-idp')

    async def delete_user(self, user_id: str):
        self.client.admin_delete_user(
            UserPoolId=self.user_pool_id,
            Username=user_id
        )
