from ..api.aws_cognito_base_class import AwsCognitoBaseClass

class FakeAwsCognitoClient(AwsCognitoBaseClass):

    async def delete_user(self, user_id: str):
        pass
