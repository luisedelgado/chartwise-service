import boto3
import json
import os

from ..api.aws_secret_manager_base_class import AwsSecretManagerBaseClass

class AwsSecretManagerClient(AwsSecretManagerBaseClass):

    def get_rds_secret(self, secret_id: str) -> str:
        region = os.environ.get("AWS_SERVICES_REGION")
        session = boto3.session.Session()
        client = session.client(
            service_name="secretsmanager",
            region_name=region
        )

        try:
            response = client.get_secret_value(
                SecretId=secret_id
            )
        except Exception as e:
            raise Exception(e)

        secret = json.loads(response["SecretString"])
        return secret
