from fastapi import Depends, Header

from ...dependencies.dependency_container import AwsCognitoBaseClass, dependency_container

def get_user_info(
    auth_token: str = Header(..., description="Bearer Cognito ID token"),
    cognito_client: AwsCognitoBaseClass = Depends(dependency_container.inject_aws_cognito_client),
):
    """
    This module contains utility functions for verifying user authentication
    in a FastAPI application using AWS Cognito.
    """
    return cognito_client.verify_cognito_token(auth_token)
