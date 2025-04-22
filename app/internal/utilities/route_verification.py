from fastapi import Depends

from ...dependencies.dependency_container import AwsCognitoBaseClass, dependency_container

def get_user_info(
    cognito_client: AwsCognitoBaseClass = Depends(dependency_container.inject_aws_cognito_client)
):
    return cognito_client.verify_cognito_token()
