import boto3
import os

from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class AwsCognitoClient(AwsCognitoBaseClass):

    def __init__(self):
        self.user_pool_id = os.environ.get("AWS_COGNITO_USER_POOL_ID")
        self.client = boto3.client(
            'cognito-idp',
            region_name=os.environ.get("AWS_SERVICES_REGION"),
        )

    async def delete_user(self, user_id: str):
        try:
            self.client.admin_delete_user(
                UserPoolId=self.user_pool_id,
                Username=user_id
            )
        except Exception as e:
            raise Exception(f"Error deleting user: {e}")
